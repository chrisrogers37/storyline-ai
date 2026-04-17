/** Backend instance summary returned by GET /api/instances. */
export interface Instance {
  chat_settings_id: string;
  telegram_chat_id: number;
  display_name: string;
  media_count: number;
  posts_per_day: number;
  is_paused: boolean;
  last_post_at: string | null;
  instance_role: string;
}
