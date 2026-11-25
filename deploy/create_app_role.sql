-- Somente no PostgreSQL NOVO e exclusivo deste sistema, pelo console psql administrativo.
-- Se o papel já existir, ON_ERROR_STOP interrompe sem trocar a senha de uma conta existente.
\set ON_ERROR_STOP on
CREATE ROLE estoque_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
\password estoque_app
GRANT CONNECT ON DATABASE estoque_brasilcacau TO estoque_app;
\connect estoque_brasilcacau
GRANT USAGE, CREATE ON SCHEMA public TO estoque_app;
