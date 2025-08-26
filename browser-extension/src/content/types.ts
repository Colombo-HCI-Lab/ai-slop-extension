export type ChatMessage = {
  role: 'user' | 'assistant';
  message: string;
  created_at: string;
};

export type ChatHistoryResponse = {
  messages: ChatMessage[];
  total_messages?: number;
};
