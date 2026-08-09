# -*- coding: utf-8 -*-
"""
PP-OCRv6 (ncnn) inference pipeline, ported from LiteOCR C++ engine:
  https://github.com/futz12/LiteOCR

det : PP-OCRv6_tiny_det   (language agnostic, 1.9MB)
rec : PP-OCRv6_small_rec  (multilingual 18708-char dict, covers zh/en/ja)
"""

from __future__ import annotations

import math
import os
from typing import List, Optional, Tuple

import cv2
import numpy as np
import ncnn
import pyclipper

DET_MEAN = [0.485 * 255.0, 0.456 * 255.0, 0.406 * 255.0]
DET_NORM = [1.0 / (0.229 * 255.0), 1.0 / (0.224 * 255.0), 1.0 / (0.225 * 255.0)]
DET_STRIDE = 32

REC_MEAN = [127.5, 127.5, 127.5]
REC_NORM = [1.0 / 127.5, 1.0 / 127.5, 1.0 / 127.5]
REC_HEIGHT = 48

THRESHOLD = 0.3        # binary threshold for det prob map
BOX_THRESHOLD = 0.6    # min mean prob inside a box
UNCLIP_RATIO = 1.5
MIN_SIZE = 3
MAX_CANDIDATES = 1000


class OCRBox:
    __slots__ = ("points", "score", "text", "conf")

    def __init__(self, points, score, text="", conf=0.0):
        self.points = points      # 4 x (x, y) float
        self.score = score        # det mean prob
        self.text = text
        self.conf = conf          # rec mean prob


def order_box_points(pts) -> list:
    """Order 4 points as tl, tr, br, bl."""
    s = sorted(pts, key=lambda p: p[0])
    tl, bl = (s[0], s[1]) if s[0][1] < s[1][1] else (s[1], s[0])
    tr, br = (s[2], s[3]) if s[2][1] < s[3][1] else (s[3], s[2])
    return [tl, tr, br, bl]


def _norm(ax, ay, bx, by) -> float:
    return math.hypot(ax - bx, ay - by)


class PaddleOCR:
    def __init__(self, model_dir: str, num_threads: int = 2):
        self.model_dir = model_dir

        self.det = ncnn.Net()
        self.det.opt.num_threads = num_threads
        self.det.opt.use_vulkan_compute = False
        self.det.opt.use_fp16_packed = False
        self.det.opt.use_fp16_storage = False
        self.det.opt.use_fp16_arithmetic = False
        rc = self.det.load_param(os.path.join(model_dir, "PP-OCRv6_tiny_det.param"))
        if rc != 0:
            raise RuntimeError(f"det param load failed rc={rc}")
        rc = self.det.load_model(os.path.join(model_dir, "PP-OCRv6_tiny_det.bin"))
        if rc != 0:
            raise RuntimeError(f"det bin load failed rc={rc}")

        self.rec = ncnn.Net()
        self.rec.opt.num_threads = num_threads
        self.rec.opt.use_vulkan_compute = False
        self.rec.opt.use_fp16_packed = False
        self.rec.opt.use_fp16_storage = False
        self.rec.opt.use_fp16_arithmetic = False
        rc = self.rec.load_param(os.path.join(model_dir, "PP-OCRv6_small_rec.param"))
        if rc != 0:
            raise RuntimeError(f"rec param load failed rc={rc}")
        rc = self.rec.load_model(os.path.join(model_dir, "PP-OCRv6_small_rec.bin"))
        if rc != 0:
            raise RuntimeError(f"rec bin load failed rc={rc}")

        with open(os.path.join(model_dir, "PP-OCRv6_vocab.txt"), encoding="utf-8") as f:
            self.vocab = [line.rstrip("\n") for line in f]
        self.blank = 0
        self.space = len(self.vocab) + 1  # 18709

    # ---------------- det ----------------
    def det_forward(self, img_bgr: np.ndarray) -> np.ndarray:
        h, w = img_bgr.shape[:2]
        wpad = (w + DET_STRIDE - 1) // DET_STRIDE * DET_STRIDE - w
        hpad = (h + DET_STRIDE - 1) // DET_STRIDE * DET_STRIDE - h
        top, bottom, left, right = hpad // 2, hpad - hpad // 2, wpad // 2, wpad - wpad // 2
        padded = cv2.copyMakeBorder(img_bgr, top, bottom, left, right,
                                    cv2.BORDER_CONSTANT, value=114)
        mat = ncnn.Mat.from_pixels(padded.tobytes(), ncnn.Mat.PixelType.PIXEL_BGR,
                                   padded.shape[1], padded.shape[0])
        mat.substract_mean_normalize(DET_MEAN, DET_NORM)
        ex = self.det.create_extractor()
        ex.input("in0", mat)
        ret, out = ex.extract("out0")
        if ret != 0:
            raise RuntimeError(f"det extract failed rc={ret}")
        prob = np.asarray(out.numpy())
        if prob.ndim == 3:
            prob = prob[0]
        return prob[top:top + h, left:left + w].copy()

    def _box_score(self, prob: np.ndarray, box) -> float:
        h, w = prob.shape
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        xmin = max(0, int(math.floor(min(xs))))
        xmax = min(w - 1, int(math.ceil(max(xs))))
        ymin = max(0, int(math.floor(min(ys))))
        ymax = min(h - 1, int(math.ceil(max(ys))))
        if xmin >= xmax or ymin >= ymax:
            return 0.0
        roi_w = int(xmax - xmin + 1)
        roi_h = int(ymax - ymin + 1)
        mask = np.zeros((roi_h, roi_w), dtype=np.uint8)
        shifted = np.array([(p[0] - xmin, p[1] - ymin) for p in box], dtype=np.int32)
        cv2.fillPoly(mask, [shifted], 1)
        region = prob[ymin:ymax + 1, xmin:xmax + 1]
        vals = region[mask > 0]
        return float(vals.mean()) if vals.size else 0.0

    def _unclip(self, box, ratio: float):
        area = cv2.contourArea(np.array(box, dtype=np.float32))
        length = cv2.arcLength(np.array(box, dtype=np.float32), True)
        if length < 1e-6:
            return box
        distance = area * ratio / length
        pc = pyclipper.PyclipperOffset()
        pc.AddPath([(float(x), float(y)) for x, y in box],
                   pyclipper.JT_ROUND, pyclipper.ET_CLOSEDPOLYGON)
        sol = pc.Execute(distance)
        if not sol or not sol[0]:
            return box
        return [(float(p[0]), float(p[1])) for p in sol[0]]

    def detect(self, img_bgr: np.ndarray) -> List[OCRBox]:
        h, w = img_bgr.shape[:2]
        prob = self.det_forward(img_bgr)
        binary = (prob > THRESHOLD).astype(np.uint8) * 255
        contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        contours = contours[:MAX_CANDIDATES]

        ws = w / prob.shape[1]
        hs = h / prob.shape[0]
        boxes: List[OCRBox] = []
        for contour in contours:
            pts = contour.reshape(-1, 2)
            if len(pts) < 4:
                continue
            rect = cv2.minAreaRect(pts.astype(np.float32))
            sside = min(rect[1])
            if sside < MIN_SIZE:
                continue
            rbox = cv2.boxPoints(rect)
            score = self._box_score(prob, rbox)
            if score < BOX_THRESHOLD:
                continue
            expanded = self._unclip(rbox, UNCLIP_RATIO)
            if len(expanded) < 4:
                continue
            exp_contour = np.array([(int(p[0]), int(p[1])) for p in expanded], dtype=np.int32)
            rect2 = cv2.minAreaRect(exp_contour)
            sside2 = min(rect2[1])
            if sside2 < MIN_SIZE + 2:
                continue
            angle = rect2[2]
            if angle >= 90.0:
                angle -= 180.0
            elif angle < -90.0:
                angle += 180.0

            mapped = cv2.boxPoints(rect2)
            mapped[:, 0] = np.clip(np.round(mapped[:, 0] * ws), 0, w)
            mapped[:, 1] = np.clip(np.round(mapped[:, 1] * hs), 0, h)
            cx, cy = mapped[:, 0].mean(), mapped[:, 1].mean()
            size = (rect2[1][0] * ws, rect2[1][1] * hs)
            final = cv2.boxPoints(((cx, cy), size, angle))
            boxes.append(OCRBox([(float(p[0]), float(p[1])) for p in final], score))

        # order by top-left then bubble by x within 10px rows (port of LiteOCR)
        def top_left(b: OCRBox):
            p0, p1, p3 = b.points[0], b.points[1], b.points[3]
            cxm = sum(p[0] for p in b.points) / 4.0
            cym = sum(p[1] for p in b.points) / 4.0
            b_w = _norm(*p0, *p1)
            b_h = _norm(*p0, *p3)
            ang = math.degrees(math.atan2(p1[1] - p0[1], p1[0] - p0[0]))
            pts = cv2.boxPoints(((cxm, cym), (b_w, b_h), ang))
            return order_box_points(pts)[0]

        keyed = [(top_left(b), b) for b in boxes]
        keyed.sort(key=lambda kv: (kv[0][1], kv[0][0]))
        for i in range(len(keyed) - 1):
            for j in range(i, -1, -1):
                if (abs(keyed[j + 1][0][1] - keyed[j][0][1]) < 10.0
                        and keyed[j + 1][0][0] < keyed[j][0][0]):
                    keyed[j], keyed[j + 1] = keyed[j + 1], keyed[j]
                else:
                    break
        return [b for _, b in keyed]

    # ---------------- rec ----------------
    def _rec_forward(self, roi_bgr: np.ndarray) -> Tuple[np.ndarray, float]:
        h, w = roi_bgr.shape[:2]
        target_w = int(w * REC_HEIGHT / h)
        if target_w <= 0:
            return np.zeros((0, 0), dtype=np.float32), 0.0
        mat = ncnn.Mat.from_pixels_resize(
            roi_bgr.tobytes(), ncnn.Mat.PixelType.PIXEL_BGR,
            w, h, target_w, REC_HEIGHT)
        mat.substract_mean_normalize(REC_MEAN, REC_NORM)
        ex = self.rec.create_extractor()
        ex.input("in0", mat)
        ret, out = ex.extract("out0")
        if ret != 0:
            raise RuntimeError(f"rec extract failed rc={ret}")
        probs = np.asarray(out.numpy())  # (T, C)
        return probs, float(target_w)

    @staticmethod
    def _ctc_decode(probs: np.ndarray, vocab, blank=0, space=None) -> Tuple[str, float]:
        text = ""
        scores = []
        prev = -1
        for row in probs:
            idx = int(np.argmax(row))
            if idx == blank or idx == prev:
                prev = idx
                continue
            prev = idx
            if 1 <= idx <= len(vocab):
                text += vocab[idx - 1]
                scores.append(float(row[idx]))
            elif space is not None and idx == space:
                if not text or text[-1] != " ":
                    text += " "
                    scores.append(float(row[idx]))
        conf = float(np.mean(scores)) if scores else 0.0
        return text, conf

    def recognize_line(self, img_bgr: np.ndarray, box: OCRBox) -> OCRBox:
        p0, p1, p2, p3 = box.points
        cx = sum(p[0] for p in box.points) / 4.0
        cy = sum(p[1] for p in box.points) / 4.0
        b_w = _norm(*p0, *p1)
        b_h = _norm(*p0, *p3)
        ang = math.degrees(math.atan2(p1[1] - p0[1], p1[0] - p0[0]))
        pts = cv2.boxPoints(((cx, cy), (b_w, b_h), ang))
        ordered = order_box_points(pts)
        tl, tr, br, bl = ordered
        crop_w = max(_norm(*tl, *tr), _norm(*br, *bl))
        crop_h = max(_norm(*tl, *bl), _norm(*tr, *br))
        if crop_w < 1 or crop_h < 1:
            return box
        src = np.array([tl, tr, br, bl], dtype=np.float32)
        dst = np.array([[0, 0], [crop_w, 0], [crop_w, crop_h], [0, crop_h]],
                       dtype=np.float32)
        m = cv2.getPerspectiveTransform(src, dst)
        warp = cv2.warpPerspective(img_bgr, m,
                                   (int(crop_w), int(crop_h)),
                                   flags=cv2.INTER_LINEAR,
                                   borderValue=(0, 0, 0))
        if warp.shape[0] / float(warp.shape[1]) >= 1.5:
            warp = cv2.rotate(warp, cv2.ROTATE_90_COUNTERCLOCKWISE)
        probs, _ = self._rec_forward(warp)
        if probs.size == 0:
            return box
        text, conf = self._ctc_decode(probs, self.vocab, blank=self.blank, space=self.space)
        box.text = text
        box.conf = conf
        return box

    def ocr(self, img_bgr: np.ndarray) -> List[OCRBox]:
        boxes = self.detect(img_bgr)
        for b in boxes:
            self.recognize_line(img_bgr, b)
        return boxes
