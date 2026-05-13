import { z } from 'zod';

// D-53: Zod schemas for /login mode state machine. Messages are
// sentence-case and specific per copy-voice.md (no "Please", no exclamation,
// no generic "Required" — explain what to do).

export const loginSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1, 'Enter your password.'),
});
export type LoginInput = z.infer<typeof loginSchema>;

export const forgotSchema = z.object({
  email: z.string().email(),
});
export type ForgotInput = z.infer<typeof forgotSchema>;

export const resetSchema = z.object({
  token: z.string().min(1),
  newPassword: z.string().min(8, 'At least 8 characters.'),
});
export type ResetInput = z.infer<typeof resetSchema>;
