CREATE TABLE user{
    id uuid PRIMARY KEY DEFAULT uuidv7(),
    name varchar(255) NOT NULL,
    email varchar(255) NOT NULL,
    password varchar(255) NOT NULL UNIQUE (email),
    created_at timestamp DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp DEFAULT CURRENT_TIMESTAMP,
    }
