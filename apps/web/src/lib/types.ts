export type Id = string;
export type Program = { id: Id; organization_id: string; name: string; description: string; start_date: string };
export type Task = {
  id: Id; code: string; name: string; owner: string; team_id?: Id; duration_days: number;
  baseline_start: string; baseline_end: string; forecast_start?: string; forecast_end?: string; status: string;
};
export type ScheduleTask = Omit<Task, "forecast_start" | "forecast_end"> & {
  earliest_start: string; earliest_finish: string; latest_start: string; latest_finish: string;
  slack_days: number; is_critical: boolean; forecast_start: string; forecast_finish: string;
};
export type Schedule = {
  tasks: ScheduleTask[]; critical_path: Id[]; project_finish: string; target_finish: string;
  variance_days: number; available_slack_days: number; dependency_paths: Record<Id, Id[]>;
};
export type Risk = {
  id: Id; code: string; description: string; probability: number; impact: number; score: number;
  severity: string; owner: string; mitigation: string; status: string;
};
export type Dashboard = {
  program_health: Record<string, string>; current_milestone?: Record<string, unknown>;
  target_completion: string; forecast_completion: string; critical_path: string[];
  top_blocker?: Task; highest_risks: Risk[]; required_decisions: Record<string, unknown>[];
  hardware_warnings: Record<string, unknown>[]; counts: Record<string, number>;
};
export type Snapshot = {
  program: Program; resources: Record<string, Record<string, any>[]>; hardware_warnings: Record<string, any>[];
};
