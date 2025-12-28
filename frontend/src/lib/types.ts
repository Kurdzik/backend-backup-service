export interface ApiResponse<T = any> {
  message: string;
  data: T;
  status: number;
  detail?: string;
}