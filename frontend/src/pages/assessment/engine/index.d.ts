export interface AssessmentRuntime {
  setActive(active: boolean): void;
  dispose(): void;
}
export function createAssessmentRuntime(root: HTMLElement, navigate: (path: string) => void): AssessmentRuntime;
