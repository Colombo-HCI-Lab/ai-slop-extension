import { IsString } from 'class-validator';

export class SendMessageDto {
  @IsString()
  postId: string;

  @IsString()
  message: string;
}

export class ChatResponse {
  id: string;
  postId: string;
  role: string;
  message: string;
  createdAt: Date;
}

export class ChatHistoryResponse {
  messages: ChatResponse[];
}
