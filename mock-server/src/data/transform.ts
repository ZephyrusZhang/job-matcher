import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { v5 as uuidv5 } from 'uuid';

const UUID_NAMESPACE = '6ba7b810-9dad-11d1-80b4-00c04fd430c8';

interface RawJob {
  title: string;
  category: string;
  location: string;
  job_type: string;
  responsibilities: string;
  requirements: string;
  department: string;
  department_product: string;
  education: string;
  experience: string;
  posted_date: string | null;
  source_url: string;
  summary: string;
}

export interface Company {
  id: string;
  name: string;
}

export interface TransformedJob {
  id: string;
  title: string;
  category: string;
  location: string;
  job_type: string;
  responsibilities: string;
  requirements: {
    must_have: string[];
    nice_to_have: string[];
  };
  department: string;
  department_product: string;
  education: string;
  experience: string;
  posted_date: string;
  source_url: string;
  summary: string;
  company: Company;
  created_at: string;
  is_favorited?: boolean;
}

const COMPANY_MAP: Record<string, Company> = {
  bytedance: { id: 'bytedance', name: '字节跳动' },
  tencent: { id: 'tencent', name: '腾讯' },
};

function splitRequirements(raw: string): { must_have: string[]; nice_to_have: string[] } {
  // Split by patterns like "1、", "2、", "1.", "2." etc.
  const parts = raw
    .split(/\d+[、.]/)
    .map((s) => s.trim())
    .filter((s) => s.length > 0);

  const must_have = parts.slice(0, 3);
  const nice_to_have = parts.slice(3);
  return { must_have, nice_to_have };
}

function randomRecentDate(withinDays: number = 30): string {
  const now = Date.now();
  const offset = Math.floor(Math.random() * withinDays * 24 * 60 * 60 * 1000);
  return new Date(now - offset).toISOString().split('T')[0]!;
}

function transformJob(raw: RawJob, companyKey: string): TransformedJob {
  const company = COMPANY_MAP[companyKey]!;
  const id = uuidv5(raw.source_url, UUID_NAMESPACE);
  const posted_date = raw.posted_date ?? randomRecentDate();
  const requirements = splitRequirements(raw.requirements);
  const created_at = new Date().toISOString();

  return {
    id,
    title: raw.title,
    category: raw.category,
    location: raw.location,
    job_type: raw.job_type,
    responsibilities: raw.responsibilities,
    requirements,
    department: raw.department,
    department_product: raw.department_product,
    education: raw.education,
    experience: raw.experience,
    posted_date,
    source_url: raw.source_url,
    summary: raw.summary,
    company,
    created_at,
  };
}

let cachedJobs: TransformedJob[] | null = null;

export function loadJobs(): TransformedJob[] {
  if (cachedJobs) return cachedJobs;

  const tmpDir = join(import.meta.dirname ?? __dirname, '..', '..', '..', 'tmp');
  const files: { file: string; companyKey: string }[] = [
    { file: 'bytedance.json', companyKey: 'bytedance' },
    { file: 'tencent.json', companyKey: 'tencent' },
  ];

  const allJobs: TransformedJob[] = [];

  for (const { file, companyKey } of files) {
    try {
      const raw = JSON.parse(readFileSync(join(tmpDir, file), 'utf-8')) as { jobs: RawJob[] };
      for (const job of raw.jobs) {
        allJobs.push(transformJob(job, companyKey));
      }
    } catch (e) {
      console.warn(`Warning: could not load ${file}:`, e);
    }
  }

  cachedJobs = allJobs;
  return allJobs;
}
