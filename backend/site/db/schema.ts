import {sqliteTable,text,integer} from 'drizzle-orm/sqlite-core';
export const competitionCache=sqliteTable('competition_cache',{
 noticeId:text('notice_id').primaryKey(),payload:text('payload'),lastSuccess:integer('last_success'),lastAttempt:integer('last_attempt'),lastError:text('last_error'),lockUntil:integer('lock_until').notNull().default(0),lockToken:text('lock_token')
});
