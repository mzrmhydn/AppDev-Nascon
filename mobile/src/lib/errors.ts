// Plain-language text for every error code in spec Appendix B (+ app-side NETWORK). Spec §8.6: never show raw codes.
// The server's `message` is never shown; only our own text keyed by `code`.

const TEXT: Record<string, string> = {
  VALIDATION_ERROR: 'Some details are missing or not in the right format. Please check the form and try again.',
  UNKNOWN_EVENT_TYPE: 'That scoring event does not exist for this sport.',
  INVALID_DISCOUNT_CODE: 'That discount code is not valid.',
  UNAUTHENTICATED: 'Your session has ended or the email/password is wrong. Please sign in again.',
  PAYMENT_DECLINED: 'Your card was declined. You have not been charged.',
  PAYMENT_CAPTURE_FAILED: 'The payment could not be completed. You have not been charged.',
  FORBIDDEN: 'Your account is not allowed to do this.',
  SPORT_NOT_FOUND: 'This sport could not be found.',
  MATCH_NOT_FOUND: 'This match could not be found.',
  LEAGUE_NOT_FOUND: 'This league could not be found.',
  EVENT_NOT_FOUND: 'The event you are correcting could not be found.',
  PLAYER_NOT_FOUND: 'This player could not be found.',
  SQUAD_NOT_FOUND: 'This club or squad could not be found.',
  VARIANT_NOT_FOUND: 'This product option is no longer available.',
  SPORT_EXISTS: 'A sport with this id already exists.',
  LEAGUE_EXISTS: 'A league with this id already exists.',
  MATCH_EXISTS: 'This match already exists.',
  DUPLICATE_EVENT_ID: 'This event was already recorded with different details.',
  DUPLICATE_ORDER_ID: 'This order number was already used for a different order.',
  ILLEGAL_TRANSITION: 'The match cannot move to that stage right now (for example, it has already started or ended).',
  MATCH_NOT_IN_PROGRESS: 'Scores can only be added while the match is in progress.',
  TIE_NOT_ALLOWED: 'This sport does not allow a draw. Record a tie-break winner before ending the match.',
  INNINGS_COMPLETE: 'This team’s innings is already over, so no more scoring can be added for it.',
  SERIES_ALREADY_DECIDED: 'The series is already decided, so no more rounds can be added.',
  INVALID_COMPENSATION: 'This event cannot be corrected (it may already be corrected, or it is not a scoring event).',
  NO_VALID_PAIRING: 'No fair pairing is possible for this round.',
  OUT_OF_STOCK: 'Sorry, this item just sold out. Your card was not charged.',
  CROSS_TENANT_TRANSFER: 'Players can only move between clubs of the same organisation.',
  NOT_IN_SQUAD: 'This player is no longer in that squad — someone may have moved them already.',
  TRANSFER_WINDOW_CLOSED: 'The transfer window is closed on that date.',
  PLAYER_ON_LOAN: 'This player is on loan and cannot be moved until the loan ends.',
  SQUAD_FULL: 'The destination squad is full.',
  MIN_POSITION_VIOLATION: 'The squad would not have enough players in this position after the move.',
  INVALID_BASE_VERSION: 'The data on this phone did not match the server, so the server’s version was kept.',
  PAYLOAD_TOO_LARGE: 'That request is too large to send.',
  RATE_LIMITED: 'Too many requests at once. Please wait a few seconds and try again.',
  INTERNAL_ERROR: 'Something went wrong on the server. Please try again.',
  NETWORK: 'Can’t reach the server. Check your connection or the server address in Settings.',
};

/** Friendly text for an error code. Unknown codes still get a plain sentence (never the code itself). */
export function friendlyError(code: string | null | undefined): string {
  if (!code) return 'Something went wrong. Please try again.';
  return TEXT[code] ?? 'Something went wrong. Please try again.';
}

/** Thrown by api.ts for every failed request. */
export class ApiError extends Error {
  status: number;
  code: string;
  details: Record<string, any>;
  constructor(status: number, code: string, details: Record<string, any> = {}) {
    super(friendlyError(code));
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

/** Text for any thrown value (ApiError or unexpected). */
export function messageOf(e: unknown): string {
  if (e instanceof ApiError) return e.message;
  return friendlyError(null);
}
