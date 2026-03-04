import { pgTable, uuid, text, timestamp, boolean } from "drizzle-orm/pg-core"

export const waitlistSignups = pgTable("waitlist_signups", {
  id: uuid("id").defaultRandom().primaryKey(),
  email: text("email").notNull().unique(),
  name: text("name"),
  instagramHandle: text("instagram_handle"),
  contentCount: text("content_count"),
  createdAt: timestamp("created_at").defaultNow().notNull(),
  notifiedAdmin: boolean("notified_admin").default(false),
  invitedAt: timestamp("invited_at"),
  notes: text("notes"),
})
