import fs from 'fs/promises'
import path from 'path'
import os from 'os'

export function getDataDir(): string {
  return process.env.ARL_DATA_DIR ?? path.join(os.homedir(), '.ai-rule-learning')
}

export async function ensureDataDir(): Promise<void> {
  const dir = getDataDir()
  await fs.mkdir(dir, { recursive: true })
}

export async function readJsonl<T = Record<string, unknown>>(filename: string): Promise<T[]> {
  await ensureDataDir()
  const filePath = path.join(getDataDir(), filename)
  try {
    const content = await fs.readFile(filePath, 'utf-8')
    const lines = content.split('\n').filter((line) => line.trim() !== '')
    return lines.map((line) => JSON.parse(line) as T)
  } catch (err: unknown) {
    if ((err as NodeJS.ErrnoException).code === 'ENOENT') {
      return []
    }
    throw err
  }
}

export async function appendJsonl(filename: string, record: unknown): Promise<void> {
  await ensureDataDir()
  const filePath = path.join(getDataDir(), filename)
  const line = JSON.stringify(record) + '\n'
  await fs.appendFile(filePath, line, 'utf-8')
}

export async function writeJsonl(filename: string, records: unknown[]): Promise<void> {
  await ensureDataDir()
  const filePath = path.join(getDataDir(), filename)
  const content = records.map((r) => JSON.stringify(r)).join('\n') + (records.length > 0 ? '\n' : '')
  await fs.writeFile(filePath, content, 'utf-8')
}
