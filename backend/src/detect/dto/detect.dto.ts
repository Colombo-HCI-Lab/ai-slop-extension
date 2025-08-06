export class DetectDto {
  content: string;
  postId: string;
  author?: string;
  metadata?: {
    timestamp?: string;
    url?: string;
  };
}
