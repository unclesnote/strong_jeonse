CREATE TABLE `competition_cache` (
	`notice_id` text PRIMARY KEY NOT NULL,
	`payload` text,
	`last_success` integer,
	`last_attempt` integer,
	`last_error` text,
	`lock_until` integer DEFAULT 0 NOT NULL,
	`lock_token` text
);
