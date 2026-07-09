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

// PROD-06-03: forced first-login rotation. current_password / new_password
// match the Wave 2 POST /auth/change-password contract; confirm_password is a
// client-only guard cross-checked via .refine (the backend never sees it).
export const changePasswordSchema = z
  .object({
    current_password: z.string().min(1, 'Enter your current password.'),
    new_password: z.string().min(8, 'At least 8 characters.'),
    confirm_password: z.string().min(1, 'Confirm your new password.'),
  })
  .refine((d) => d.new_password === d.confirm_password, {
    message: "Passwords don't match.",
    path: ['confirm_password'],
  });
export type ChangePasswordInput = z.infer<typeof changePasswordSchema>;
