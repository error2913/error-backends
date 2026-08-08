import path from 'node:path';
import { existsSync, mkdirSync } from 'node:fs';
import fsp from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { createWorker } from 'tesseract.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const LANG_DIR = process.env.OCR_LANG_DIR || path.join(__dirname, 'lang-data');
const CACHE_DIR = process.env.OCR_CACHE_DIR || path.join(__dirname, 'cache');
const DEFAULT_LANG = process.env.OCR_DEFAULT_LANG || 'chi_sim+eng';
const LANG_MIRROR = process.env.OCR_LANG_MIRROR || 'https://tessdata.projectnaptha.com/4.0.0';

let worker = null;
let workerLang = null;
let queue = Promise.resolve();
let pendingJobs = 0;
let totalJobs = 0;

function enqueue(fn) {
  pendingJobs += 1;
  totalJobs += 1;
  const run = queue.then(fn, fn);
  queue = run.then(
    () => {
      pendingJobs -= 1;
    },
    () => {
      pendingJobs -= 1;
    }
  );
  return run;
}

// 确保 lang-data 里有请求的语言包，缺失则自动下载（.traineddata.gz）
async function ensureLangFiles(langs) {
  const list = typeof langs === 'string'
    ? langs.split('+').map((s) => s.trim()).filter(Boolean)
    : [];
  if (list.length === 0) return;
  mkdirSync(LANG_DIR, { recursive: true });
  for (const lang of list) {
    const file = path.join(LANG_DIR, `${lang}.traineddata.gz`);
    if (existsSync(file)) continue;
    const url = `${LANG_MIRROR}/${lang}.traineddata.gz`;
    console.log(`[ocr] 语言包缺失，下载 ${url}`);
    const res = await fetch(url, { signal: AbortSignal.timeout(120_000) });
    if (!res.ok) {
      throw new Error(`语言包下载失败 ${lang}: HTTP ${res.status}`);
    }
    const buf = Buffer.from(await res.arrayBuffer());
    await fsp.writeFile(file, buf);
    console.log(`[ocr] 语言包已就绪 ${lang} (${(buf.length / 1024 / 1024).toFixed(2)} MB)`);
  }
}

async function getWorker(lang) {
  await ensureLangFiles(lang);
  if (!worker) {
    mkdirSync(LANG_DIR, { recursive: true });
    mkdirSync(CACHE_DIR, { recursive: true });
    worker = await createWorker(lang, 1, {
      langPath: LANG_DIR,
      cachePath: CACHE_DIR,
      gzip: true,
      logger: (m) => {
        if (process.env.OCR_DEBUG === '1') {
          console.log(`[tesseract] ${m.status}`);
        }
      },
    });
    workerLang = lang;
  } else if (workerLang !== lang) {
    await worker.reinitialize(lang, 1);
    workerLang = lang;
  }
  return worker;
}

/**
 * 对图片 Buffer 执行 OCR（串行队列，单 worker）。
 * options:
 *   lang      string  语言，多个用 + 连接，如 chi_sim+eng
 *   psm       number  页面分割模式，如 6 表示单文本块
 *   whitelist string  字符白名单，如 0123456789
 */
export async function recognize(buffer, options = {}) {
  const { lang = DEFAULT_LANG, psm = null, whitelist = null } = options;
  return enqueue(async () => {
    const w = await getWorker(lang);
    if (psm !== null && psm !== undefined) {
      await w.setParameters({ tessedit_pageseg_mode: Number(psm) });
    }
    if (whitelist) {
      await w.setParameters({ tessedit_char_whitelist: whitelist });
    }
    const { data } = await w.recognize(buffer, {}, { text: true, confidence: true, blocks: true });
    if (whitelist) {
      // 复位白名单，避免残留影响后续请求
      await w.setParameters({ tessedit_char_whitelist: '' });
    }
    return data;
  });
}

export function stats() {
  return {
    engine: 'tesseract.js',
    workerReady: worker !== null,
    workerLang,
    pendingJobs,
    totalJobs,
    defaultLang: DEFAULT_LANG,
    langMirror: LANG_MIRROR,
    langDir: LANG_DIR,
    cacheDir: CACHE_DIR,
  };
}

export async function shutdown() {
  if (worker) {
    await worker.terminate();
    worker = null;
    workerLang = null;
  }
}
