CREATE TABLE auth_tokens (
	id INTEGER NOT NULL, 
	token VARCHAR(64) NOT NULL, 
	user_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE bank_info (
	id INTEGER NOT NULL, 
	bank_name VARCHAR(120) NOT NULL, 
	phone VARCHAR(40) NOT NULL, 
	id_number VARCHAR(40) NOT NULL, 
	account_type VARCHAR(40) NOT NULL, 
	holder_name VARCHAR(120) NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE duel_types (
	id INTEGER NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	logic_rule VARCHAR(60) NOT NULL, 
	description TEXT NOT NULL, 
	is_matchup BOOLEAN NOT NULL, 
	is_morocha BOOLEAN NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE duels (
	id INTEGER NOT NULL, 
	duel_type_id INTEGER NOT NULL, 
	race_number INTEGER NOT NULL, 
	race_datetime DATETIME NOT NULL, 
	horse_creator INTEGER NOT NULL, 
	horse_opponent INTEGER NOT NULL, 
	horse_creator_name VARCHAR(120) NOT NULL, 
	horse_opponent_name VARCHAR(120) NOT NULL, 
	horse_creator_2 INTEGER, 
	horse_opponent_2 INTEGER, 
	horse_creator_2_name VARCHAR(120), 
	horse_opponent_2_name VARCHAR(120), 
	horse_acceptor INTEGER, 
	stake FLOAT NOT NULL, 
	fee_percentage FLOAT NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	creator_id INTEGER NOT NULL, 
	acceptor_id INTEGER, 
	winner_id INTEGER, 
	winner_horse_number INTEGER, 
	commission_amount FLOAT, 
	payout_amount FLOAT, 
	resolution_note TEXT, 
	created_at DATETIME NOT NULL, 
	accepted_at DATETIME, 
	resolved_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(duel_type_id) REFERENCES duel_types (id), 
	FOREIGN KEY(creator_id) REFERENCES users (id), 
	FOREIGN KEY(acceptor_id) REFERENCES users (id), 
	FOREIGN KEY(winner_id) REFERENCES users (id)
);

CREATE TABLE official_results (
	id INTEGER NOT NULL, 
	race_number INTEGER NOT NULL, 
	position INTEGER NOT NULL, 
	horse_number INTEGER NOT NULL, 
	horse_name VARCHAR(120) NOT NULL, 
	recorded_by INTEGER, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_official_race_horse UNIQUE (race_number, horse_number), 
	FOREIGN KEY(recorded_by) REFERENCES users (id)
);

CREATE TABLE race_entries (
	id INTEGER NOT NULL, 
	race_number INTEGER NOT NULL, 
	race_datetime DATETIME NOT NULL, 
	horse_number INTEGER NOT NULL, 
	horse_name VARCHAR(120) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_race_horse UNIQUE (race_number, horse_number)
);

CREATE TABLE top_up_requests (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	amount FLOAT NOT NULL, 
	reference VARCHAR(80) NOT NULL, 
	wallet_phone VARCHAR(40) NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	created_at DATETIME NOT NULL, 
	reviewed_at DATETIME, 
	reviewed_by INTEGER, 
	note TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(reviewed_by) REFERENCES users (id)
);

CREATE TABLE users (
	id INTEGER NOT NULL, 
	username VARCHAR(64) NOT NULL, 
	password_hash VARCHAR(160) NOT NULL, 
	balance FLOAT NOT NULL, 
	role VARCHAR(16) NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE withdrawal_requests (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	amount FLOAT NOT NULL, 
	destination_phone VARCHAR(40) NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	created_at DATETIME NOT NULL, 
	reviewed_at DATETIME, 
	reviewed_by INTEGER, 
	note TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(reviewed_by) REFERENCES users (id)
);

-- Data for duel_types table
INSERT INTO duel_types (id, name, logic_rule, description, is_matchup, is_morocha) VALUES (1, 'PELO a PELO', 'OFFICIAL_FINISH', 'Ganas con el 1ro.', 0, 0);
INSERT INTO duel_types (id, name, logic_rule, description, is_matchup, is_morocha) VALUES (2, '1y2N', 'OFFICIAL_FINISH', 'Ganas con el 1ro, con el 2do Pierdes la Mitad.', 0, 0);
INSERT INTO duel_types (id, name, logic_rule, description, is_matchup, is_morocha) VALUES (3, '2N', 'OFFICIAL_FINISH', 'Ganas con el 1ro, con el 2do Empatas.', 0, 0);
INSERT INTO duel_types (id, name, logic_rule, description, is_matchup, is_morocha) VALUES (4, '2y2N', 'OFFICIAL_FINISH', 'Ganas con el 1ro, con el 2do Ganas la Mitad.', 0, 0);
INSERT INTO duel_types (id, name, logic_rule, description, is_matchup, is_morocha) VALUES (5, '2 PUESTOS', 'OFFICIAL_FINISH', 'Ganas con el 1ro y con el 2do.', 0, 0);
INSERT INTO duel_types (id, name, logic_rule, description, is_matchup, is_morocha) VALUES (6, '2y3N', 'OFFICIAL_FINISH', 'Ganas con el 1ro y el 2do, con el 3ro Pierdes la Mitad.', 0, 0);
INSERT INTO duel_types (id, name, logic_rule, description, is_matchup, is_morocha) VALUES (7, '3N', 'OFFICIAL_FINISH', 'Ganas con el 1ro y el 2do, con el 3ro Empatas.', 0, 0);
INSERT INTO duel_types (id, name, logic_rule, description, is_matchup, is_morocha) VALUES (8, '3y3N', 'OFFICIAL_FINISH', 'Ganas con el 1ro y el 2do, con el 3ro Ganas la Mitad.', 0, 0);
INSERT INTO duel_types (id, name, logic_rule, description, is_matchup, is_morocha) VALUES (9, '3 PUESTOS', 'OFFICIAL_FINISH', 'Ganas con el 1ro, 2do y el 3ro.', 0, 0);
INSERT INTO duel_types (id, name, logic_rule, description, is_matchup, is_morocha) VALUES (10, '3y4N', 'OFFICIAL_FINISH', 'Ganas con el 1ro, 2do y 3ro, con el 4to Pierdes la Mitad.', 0, 0);
INSERT INTO duel_types (id, name, logic_rule, description, is_matchup, is_morocha) VALUES (11, '4N', 'OFFICIAL_FINISH', 'Ganas con el 1ro, 2do y 3ro, con el 4to Empatas.', 0, 0);
INSERT INTO duel_types (id, name, logic_rule, description, is_matchup, is_morocha) VALUES (12, '4y4N', 'OFFICIAL_FINISH', 'Ganas con el 1ro, 2do y el 3ro, con el 4to Ganas la Mitad.', 0, 0);
INSERT INTO duel_types (id, name, logic_rule, description, is_matchup, is_morocha) VALUES (13, '4 PUESTOS', 'OFFICIAL_FINISH', 'Ganas con el 1ro, 2do, 3ro y el 4to.', 0, 0);
INSERT INTO duel_types (id, name, logic_rule, description, is_matchup, is_morocha) VALUES (14, '4y5N', 'OFFICIAL_FINISH', 'Ganas con el 1ro, 2do, 3ro y 4to, con el 5to Pierdes la Mitad.', 0, 0);
INSERT INTO duel_types (id, name, logic_rule, description, is_matchup, is_morocha) VALUES (15, '5N', 'OFFICIAL_FINISH', 'Ganas con el 1ro, 2do, 3ro y 4to, con el 5to Empatas.', 0, 0);
INSERT INTO duel_types (id, name, logic_rule, description, is_matchup, is_morocha) VALUES (16, '5y5N', 'OFFICIAL_FINISH', 'Ganas con el 1ro, 2do, 3ro y el 4to, con el 5to Ganas la Mitad.', 0, 0);
INSERT INTO duel_types (id, name, logic_rule, description, is_matchup, is_morocha) VALUES (17, '5 PUESTOS', 'OFFICIAL_FINISH', 'Ganas con el 1ro, 2do, 3ro, 4to y el 5to.', 0, 0);
INSERT INTO duel_types (id, name, logic_rule, description, is_matchup, is_morocha) VALUES (18, 'MARCAS', 'OFFICIAL_FINISH', 'Caballo vs Caballo.', 1, 0);
INSERT INTO duel_types (id, name, logic_rule, description, is_matchup, is_morocha) VALUES (19, 'MOROCHA', 'OFFICIAL_FINISH', '2 Caballos vs 2 Caballos.', 0, 1);
