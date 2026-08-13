/**
 * API javob turlari — hozircha qo'lda yozilgan.
 * Faza 2 oxirida OpenAPI (`/openapi.json`) dan generatsiya qilinadi va bu fayl
 * generatsiya natijasiga almashadi. Maydonlar `snake_case` — backend shunday beradi.
 */

export type Role = 'OWNER' | 'ADMIN' | 'STAFF';

export interface MeUser {
  id: number;
  telegram_id: number;
  first_name: string;
  last_name: string | null;
  username: string | null;
  phone: string | null;
  phone_verified: boolean;
}

export interface MembershipBrief {
  club_id: number;
  club_name: string;
  role: Role;
}

export interface AuthSession {
  access_token: string;
  access_expires_at: string;
  refresh_token: string;
  refresh_expires_at: string;
  user: MeUser;
  memberships: MembershipBrief[];
  is_super_admin: boolean;
  entitlements: Entitlements | null;
}

export interface ClubBrief {
  id: number;
  name: string;
  role: Role;
  org_id: number;
  status: string;
}

export interface Me extends MeUser {
  is_super_admin: boolean;
  clubs: ClubBrief[];
}

export interface Entitlements {
  plan: string | null;
  limits: Record<string, number | null>;
  features: string[];
}
