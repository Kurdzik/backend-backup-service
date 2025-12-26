export interface ApiResponse<T = Map<string, any>> {
  message: string;
  data: T;
}

