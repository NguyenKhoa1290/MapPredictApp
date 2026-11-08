import { resolve } from 'node:path';
const root = process.env.MAP_PREDICT_TEST_ROOT;
if (!root) throw new Error('Run frontend tests with the frontend Vitest configuration');
export const projectPath = (...parts: string[]) => resolve(root, ...parts);
