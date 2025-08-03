export class DetectDto {
  content: string;
  postId: string;
  metadata?: {
    author?: string;
    timestamp?: string;
    url?: string;
  };
}
