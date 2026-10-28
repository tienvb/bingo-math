// Bản sao từng chữ của "Hợp đồng REST API" và "Hợp đồng WebSocket" trong docs/spec.md.
// Mọi chỗ khác trong FE import type từ file này. Không đổi tên field ở đây khi spec chưa đổi.

// ---------------------------------------------------------------------------
// Kiểu dữ liệu dùng chung
// ---------------------------------------------------------------------------

export type Phase = "lobby" | "question" | "reveal" | "ready" | "finished";

export type RoomIcon =
  | "apple" | "banana" | "star" | "sun" | "moon" | "heart"
  | "car" | "plane" | "ball" | "flower" | "umbrella" | "fish";

export const ROOM_ICONS: readonly RoomIcon[] = [
  "apple", "banana", "star", "sun", "moon", "heart",
  "car", "plane", "ball", "flower", "umbrella", "fish",
] as const;

export type GameConfig = {
  operations: { add: boolean; sub: boolean; mul: boolean; div: boolean };
  timer_seconds: number; max_wrong: number; reveal_seconds: number; draw_only_card_numbers: boolean;
};

export type Avatar = { id: string; name: { vi: string; en: string }; image_url: string; win_animation_url: string | null; color: string };
export type PlayerInfo = { id: string; nickname: string; avatar_id: string; connected: boolean };
export type Card = number[][];            // 5x5, card[row][col], 0 = FREE tại [2][2]
export type Cell = [number, number];      // [row, col], đếm từ 0
// Quy ước (CHANGELOG 2026-10-28): marked / marked_before KHÔNG chứa ô FREE [2,2]; FE luôn coi FREE là đã khoanh.
export type Line = { type: "row" | "col" | "diag"; index: number }; // diag 0: trái-trên → phải-dưới, 1: phải-trên → trái-dưới
export type OptionKey = "A" | "B" | "C" | "D";

export type Operator = "+" | "-" | "x" | ":";
export type AnswererMode = "fixed" | "random";
export type Role = "host" | "screen" | "player";

export type Question = {
  question_id: string;
  attempt: number;                 // tăng mỗi lần sinh lại đáp án hoặc đổi người
  text: string;                    // "7 × 8 = ?" (dự phòng; FE tự dựng từ operator, a, b)
  operator: Operator;
  a: number; b: number;
  options: { key: OptionKey; value: number }[]; // luôn đủ A, B, C, D theo thứ tự
  answerer: PlayerInfo;
  deadline: string | null;         // ISO 8601 UTC, null nếu tắt đếm ngược
};

export type RevealItem = { player_id: string; nickname: string; avatar_id: string; card: Card; marked_before: Cell[]; new_cell: Cell };
export type Reveal = { number: number; seconds_per_card: number; started_at: string; items: RevealItem[] };
export type Winner = { player_id: string; nickname: string; avatar_id: string; card: Card; marked: Cell[]; lines: Line[] };

export type Snapshot = {
  pin: string; picture_code: RoomIcon[]; phase: Phase; join_url: string; config: GameConfig;
  players: PlayerInfo[];
  answerer_mode: AnswererMode | null; fixed_player_id: string | null;
  drawn: number[];                 // theo thứ tự ra
  question: Question | null; reveal: Reveal | null; winners: Winner[];
  me?: PlayerInfo; card?: Card; marked?: Cell[];  // chỉ có khi role = player
};

// ---------------------------------------------------------------------------
// Mã lỗi (REST và WebSocket). Lỗi luôn có dạng {code, message}.
// ---------------------------------------------------------------------------

export type ErrorCode =
  // chung
  | "bad_token"
  | "room_not_found"
  | "invalid_phase"
  // REST riêng
  | "invalid_config"
  | "invalid_join_url"
  | "too_many_rooms"
  | "player_not_found"
  | "no_players"
  | "fixed_player_required"
  | "no_numbers_left"
  | "nickname_taken"
  | "game_in_progress"
  | "room_full"
  | "invalid_nickname"
  | "invalid_avatar"
  // WebSocket
  | "not_your_turn"
  | "stale_question"
  | "invalid_message";             // message WS sai dạng (CHANGELOG 2026-10-28)

export const ERROR_CODES: readonly ErrorCode[] = [
  "bad_token", "room_not_found", "invalid_phase",
  "invalid_config", "invalid_join_url", "too_many_rooms", "player_not_found",
  "no_players", "fixed_player_required", "no_numbers_left", "nickname_taken",
  "game_in_progress", "room_full", "invalid_nickname", "invalid_avatar",
  "not_your_turn", "stale_question", "invalid_message",
] as const;

export type ErrorBody = { code: ErrorCode; message: string };

// ---------------------------------------------------------------------------
// REST: request / response
// ---------------------------------------------------------------------------

export type OkResponse = { ok: true };

// POST /api/rooms
export type CreateRoomRequest = { config: GameConfig; join_base_url: string };
export type CreateRoomResponse = { pin: string; picture_code: RoomIcon[]; host_token: string; screen_token: string; join_url: string };

// GET /api/rooms/{pin}
export type RoomInfoResponse = { phase: Phase; player_count: number };

// GET /api/rooms/lookup?pictures=<id>,<id>,<id>
export type LookupResponse = { pin: string };

// DELETE /api/rooms/{pin} → OkResponse
// PUT /api/rooms/{pin}/config: body GameConfig → GameConfig
export type UpdateConfigRequest = GameConfig;
export type UpdateConfigResponse = GameConfig;

// PUT /api/rooms/{pin}/join-base-url
export type JoinBaseUrlRequest = { join_base_url: string };
export type JoinBaseUrlResponse = { join_url: string };

// DELETE /api/rooms/{pin}/players/{player_id} → OkResponse

// POST /api/rooms/{pin}/start
export type StartRequest = { answerer_mode: AnswererMode; fixed_player_id: string | null };

// POST /api/rooms/{pin}/next | skip | help | end → OkResponse

// POST /api/rooms/{pin}/new-round: body {join_base_url} (tùy chọn) → OkResponse
export type NewRoundRequest = { join_base_url?: string };

// POST /api/rooms/{pin}/join
export type JoinRequest = { nickname: string; avatar_id: string };
export type JoinResponse = { player_id: string; player_token: string };

// GET /api/avatars → Avatar[]
export type AvatarsResponse = Avatar[];

// GET /api/network
export type NetworkResponse = { ips: string[]; port: number };

// GET /api/health → {ok}
export type HealthResponse = { ok: boolean };

// ---------------------------------------------------------------------------
// WebSocket
// ---------------------------------------------------------------------------

// /ws?pin=<pin>&role=<host|screen|player>&token=<token>
export const WS_CLOSE = {
  BAD_TOKEN: 4401,
  ROOM_NOT_FOUND: 4404,
  KICKED: 4403,
  ROOM_CLOSED: 4410,
} as const;

export type QuestionReason = "new" | "wrong" | "help" | "max_wrong" | "timeout" | "disconnect";
export type GameOverReason = "bingo" | "ended_by_host";
export type RoomClosedReason = "closed_by_host" | "expired";

/** Server gửi client: type → data */
export type ServerMessageMap = {
  snapshot: Snapshot;
  phase_changed: { phase: Phase };
  players_updated: { players: PlayerInfo[] };
  config_updated: { config: GameConfig };
  join_url_updated: { join_url: string };
  your_card: { card: Card; marked: Cell[] };
  game_started: { answerer_mode: AnswererMode; fixed_player_id: string | null };
  question: { question: Question; reason: QuestionReason };
  answer_result: { question_id: string; attempt: number; player_id: string; key: OptionKey; value: number; correct: boolean };
  number_drawn: { number: number; drawn: number[] };
  cell_marked: { number: number; cell: Cell };
  reveal: Reveal;
  question_skipped: { question_id: string; number: number };
  game_over: { reason: GameOverReason; winners: Winner[] };
  kicked: Record<string, never>;
  room_closed: { reason: RoomClosedReason };
  error: ErrorBody;
  pong: Record<string, never>;
};

/** Client gửi server: type → data (chỉ role = player; host/screen chỉ gửi ping) */
export type ClientMessageMap = {
  submit_answer: { question_id: string; attempt: number; key: OptionKey };
  request_help: { question_id: string };
  ping: Record<string, never>;
};

export type ServerMessageType = keyof ServerMessageMap;
export type ClientMessageType = keyof ClientMessageMap;

/** Mọi message, cả hai chiều: {"type": "<tên>", "data": {...}} */
export type WsMessage<M, K extends keyof M = keyof M> = { [T in K]: { type: T; data: M[T] } }[K];
export type ServerMessage = WsMessage<ServerMessageMap>;
export type ClientMessage = WsMessage<ClientMessageMap>;
