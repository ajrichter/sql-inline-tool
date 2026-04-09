# sql-inline-tool

idea:
https://simonwillison.net/2022/Sep/1/sqlite-duckdb-paper/

This is a tool which allows in line validation of SQL scripts pre- and post- migration

We are analyzing a SQL script to migrate to a a new SCHEMA/values

to perform in line validations
We will query Snowflake to validate certain checks around the 

We need to build DuckDB tools which can
* ingest CSV of the mappings in so we can correctly query them using Claude Code
* this needs to be flexible and reusaable
    * Ingest CSV for SQL rules
    * Convert SQL schema to CSV rules
    * Store CSV inputs as Parquet checkpoint files
* Design a flexible Query system for Claude code to use which uses DuckDB to query the files directly

* Write a set of rules on
    * how to setup dependencies
    * How to query using DuckDB
    * What are repatable queries and how to do inline validations comparing two outputs