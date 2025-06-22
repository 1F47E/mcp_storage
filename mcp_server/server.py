import anyio
import click
import random
import os
import httpx
import yaml
import psycopg2
import psycopg2.extras
import traceback
import json
import logging
import asyncio
from typing import Any, Dict, List, NamedTuple, Callable, Union, Optional
from pydantic import ValidationError
from enum import Enum
import mcp.types as types
from mcp.server.lowlevel import Server

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Define command enum
class Command(str, Enum):
    """Enum of available tool commands."""
    RANDOM_UINT64 = "random_uint64"
    POSTGRES_SCHEMAS = "postgres_schemas"
    POSTGRES_SCHEMA_DDLS = "postgres_schema_ddls"
    POSTGRES_QUERY_SELECT = "postgres_query_select"
    MYSQL_QUERY_SELECT = "mysql_query_select"
    MYSQL_SCHEMA_DDLS = "mysql_schema_ddls"

# Tool configuration structure
class ToolConfig(NamedTuple):
    name: str
    description: str
    handler: Callable[[], Any]  # Added return type hint
    properties: Dict[str, Any] = {}  # Added type hint
    required: List[str] = []  # Added type hint

# Response type alias for better readability
ToolResponse = List[Union[types.TextContent, types.ImageContent, types.EmbeddedResource]]

# Config file path
CONFIG_FILE_PATH = "config.yaml"

# Load configuration from YAML file
def load_config() -> Dict[str, Any]:
    """Load configuration from YAML file.
    
    Returns:
        Dict containing configuration values
    """
    try:
        if os.path.exists(CONFIG_FILE_PATH):
            with open(CONFIG_FILE_PATH, 'r') as file:
                config = yaml.safe_load(file)
                logger.info(f"Configuration loaded from {CONFIG_FILE_PATH}")
                return config
        else:
            logger.warning(f"Configuration file {CONFIG_FILE_PATH} not found")
            return {}
    except Exception as e:
        logger.error(f"Error loading configuration: {str(e)}")
        return {}

# Get database URL from config
def get_db_url() -> Optional[str]:
    """Get PostgreSQL database URL from configuration.
    
    Returns:
        Database URL string or None if not configured
    """
    config = load_config()
    if config and 'databases' in config and 'postgresql' in config['databases']:
        return config['databases']['postgresql'].get('url')
    return None

# Get MySQL DSN from config
def get_mysql_dsn() -> Optional[str]:
    """Get MySQL DSN from configuration.
    
    Returns:
        MySQL DSN string or None if not configured
    """
    config = load_config()
    if config and 'databases' in config and 'mysql' in config['databases']:
        return config['databases']['mysql'].get('dsn')
    return None

# Load configuration at module level
config = load_config()

# Check for database configuration at startup
db_url = get_db_url()
if db_url:
    print(f"[STARTUP] Found PostgreSQL database configuration")

# Check for MySQL configuration at startup
mysql_dsn = get_mysql_dsn()
if mysql_dsn:
    print(f"[STARTUP] Found MySQL database configuration")

# Check if at least one database configuration is available
if not db_url and not mysql_dsn:
    print(f"[STARTUP] ERROR: No database configurations found")
    print(f"[STARTUP] Please add at least one database configuration to config.yaml")
    print(f"[STARTUP] See CONFIG.md for configuration instructions")
    raise SystemExit("No database configurations found. Exiting.")


async def fetch_website(
    url: str,
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    headers = {
        "User-Agent": "MCP Test Server (github.com/modelcontextprotocol/python-sdk)"
    }
    print(f"[LOG] Fetching website: {url}")
    async with httpx.AsyncClient(follow_redirects=True, headers=headers) as client:
        response = await client.get(url)
        response.raise_for_status()
        return [types.TextContent(type="text", text=response.text)]


async def generate_random_uint64() -> ToolResponse:
    """Generate a random uint64 value.
    
    Returns:
        A list containing the text content with the random number.
    """
    logger.info("Generating random uint64 value")
    
    # Generate a random unsigned 64-bit integer
    random_value = random.randint(0, 2**64 - 1)
    
    logger.info(f"Generated random value: {random_value}")
    return [types.TextContent(type="text", text=str(random_value))]


async def postgres_schemas() -> ToolResponse:
    """Returns the PostgreSQL database schema.
    
    Returns:
        Text content containing the schema information
    """
    db_url = get_db_url()
    if not db_url:
        logger.error("PostgreSQL database configuration not found")
        return [types.TextContent(
            type="text", 
            text="Error: PostgreSQL database configuration not found in config.yaml. Please add a valid configuration."
        )]
    
    # Hide password in logs
    try:
        # Parse and mask the DATABASE_URL for logging
        if '@' in db_url:
            prefix, suffix = db_url.split('@', 1)
            protocol = prefix.split('://', 1)[0]
            masked_url = f"{protocol}://*****@{suffix}"
        else:
            masked_url = "malformed URL"
        logger.info(f"Found DATABASE_URL: {masked_url}")
    except Exception as e:
        logger.warning(f"Error masking DATABASE_URL: {str(e)}")
        logger.info("Using DATABASE_URL from configuration")
    
    try:
        # Handle 'postgres://' vs 'postgresql://' protocol
        # psycopg2 officially supports postgresql:// but can usually handle postgres:// too
        # To be safe, let's ensure it uses the correct format
        if db_url.startswith('postgres://'):
            logger.info("Converting 'postgres://' to 'postgresql://' for psycopg2 compatibility")
            db_url = 'postgresql://' + db_url[len('postgres://'):]
        
        # Connect to the database
        logger.info(f"Connecting to PostgreSQL database...")
        conn = psycopg2.connect(db_url)
        
        # Create a message with connection info
        dsn_params = conn.get_dsn_parameters()
        search_path = None
        ssl_mode = None
        
        # Extract query parameters
        if '?' in db_url:
            query_string = db_url.split('?', 1)[1]
            params = query_string.split('&')
            for param in params:
                if '=' in param:
                    key, value = param.split('=', 1)
                    if key == 'search_path':
                        search_path = value
                    elif key == 'sslmode':
                        ssl_mode = value
        
        schema_info = f"Successfully connected to PostgreSQL database.\n\n"
        schema_info += "Connection Details:\n"
        schema_info += f"- Host: {dsn_params.get('host', 'unknown')}\n"
        schema_info += f"- Database: {dsn_params.get('dbname', 'unknown')}\n"
        schema_info += f"- User: {dsn_params.get('user', 'unknown')}\n"
        schema_info += f"- Port: {dsn_params.get('port', '5432')}\n"
        schema_info += f"- Server Version: {conn.server_version}\n"
        if ssl_mode:
            schema_info += f"- SSL Mode: {ssl_mode}\n"
        if search_path:
            schema_info += f"- Search Path: {search_path}\n"
            # Apply search path explicitly
            with conn.cursor() as cursor:
                cursor.execute(f"SET search_path TO {search_path}")
                conn.commit()
        
        # Get database size
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
        db_size = cursor.fetchone()[0]
        schema_info += f"- Database Size: {db_size}\n\n"
        
        # Get schema list
        cursor.execute("""
            SELECT schema_name 
            FROM information_schema.schemata 
            WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
            ORDER BY schema_name
        """)
        schemas = cursor.fetchall()
        
        schema_info += f"Available Schemas ({len(schemas)}):\n"
        for schema in schemas:
            schema_info += f"- {schema[0]}\n"
        
        
        # Close cursor and connection
        cursor.close()
        conn.close()
        
        logger.info(f"Successfully connected to PostgreSQL database and retrieved schema information")
        return [types.TextContent(type="text", text=schema_info)]
    
    except Exception as e:
        logger.error(f"Error connecting to PostgreSQL database: {str(e)}")
        error_msg = f"Error connecting to PostgreSQL database: {e}\n\n"
        error_msg += "Please check your database configuration in config.yaml.\n"
        error_msg += "Format should be: postgresql://username:password@host:port/dbname\n"
        error_msg += "or: postgres://username:password@host:port/dbname?sslmode=disable&search_path=schema"
        
        # Print stack trace to help debug connection issues
        logger.error(traceback.format_exc())
        
        return [types.TextContent(type="text", text=error_msg)]


async def get_schema_details(conn, schema_name: str) -> str:
    """Get detailed information about tables in a specific schema.
    
    Args:
        conn: PostgreSQL connection
        schema_name: Name of the schema
        
    Returns:
        Formatted string with schema details
    """
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    details = ""
    
    try:
        # Get tables in the schema
        cursor.execute("""
            SELECT table_name, table_type
            FROM information_schema.tables
            WHERE table_schema = %s
            ORDER BY table_name
        """, (schema_name,))
        tables = cursor.fetchall()
        
        if not tables:
            return f"No tables found in schema '{schema_name}'\n"
        
        details += f"Tables in schema '{schema_name}' ({len(tables)}):\n\n"
        
        for table_info in tables:
            table_name = table_info[0]
            table_type = table_info[1]
            
            # Get column information
            cursor.execute("""
                SELECT column_name, data_type, character_maximum_length, 
                       is_nullable, column_default
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position
            """, (schema_name, table_name))
            columns = cursor.fetchall()
            
            details += f"{'TABLE' if table_type == 'BASE TABLE' else 'VIEW'}: {table_name}\n"
            details += "Columns:\n"
            
            for column in columns:
                col_name = column[0]
                data_type = column[1]
                char_max_len = column[2]
                is_nullable = column[3]
                default_val = column[4]
                
                type_display = data_type
                if char_max_len:
                    type_display += f"({char_max_len})"
                
                nullable = "NULL" if is_nullable == "YES" else "NOT NULL"
                default = f" DEFAULT {default_val}" if default_val else ""
                
                details += f"  - {col_name}: {type_display} {nullable}{default}\n"
            
            # Get primary key information
            cursor.execute("""
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu 
                  ON kcu.constraint_name = tc.constraint_name
                 AND kcu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY'
                  AND tc.table_schema = %s
                  AND tc.table_name = %s
                ORDER BY kcu.ordinal_position
            """, (schema_name, table_name))
            pk_columns = cursor.fetchall()
            
            if pk_columns:
                pk_col_names = [col[0] for col in pk_columns]
                details += f"Primary Key: {', '.join(pk_col_names)}\n"
            
            # Get foreign key information
            cursor.execute("""
                SELECT kcu.column_name, ccu.table_name AS foreign_table_name,
                       ccu.column_name AS foreign_column_name
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                  ON tc.constraint_name = kcu.constraint_name
                  AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu
                  ON ccu.constraint_name = tc.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_schema = %s
                  AND tc.table_name = %s
            """, (schema_name, table_name))
            fk_info = cursor.fetchall()
            
            if fk_info:
                details += "Foreign Keys:\n"
                for fk in fk_info:
                    details += f"  - {fk[0]} -> {fk[1]}.{fk[2]}\n"
            
            # Get index information
            cursor.execute("""
                SELECT
                    i.relname as index_name,
                    array_to_string(array_agg(a.attname), ', ') as column_names,
                    ix.indisunique as is_unique
                FROM
                    pg_class t,
                    pg_class i,
                    pg_index ix,
                    pg_attribute a,
                    pg_namespace n
                WHERE
                    t.oid = ix.indrelid
                    and i.oid = ix.indexrelid
                    and a.attrelid = t.oid
                    and a.attnum = ANY(ix.indkey)
                    and t.relkind = 'r'
                    and t.relname = %s
                    and n.oid = t.relnamespace
                    and n.nspname = %s
                GROUP BY
                    i.relname,
                    ix.indisunique
                ORDER BY
                    i.relname;
            """, (table_name, schema_name))
            indexes = cursor.fetchall()
            
            if indexes:
                details += "Indexes:\n"
                for idx in indexes:
                    unique = "UNIQUE " if idx[2] else ""
                    details += f"  - {idx[0]}: {unique}({idx[1]})\n"
            
            details += "\n"
    
    except Exception as e:
        logger.error(f"Error getting schema details: {str(e)}")
        details += f"Error retrieving detailed schema information: {str(e)}\n"
    
    finally:
        cursor.close()
    
    return details


async def postgres_schema_ddls(schema_name: str = None) -> ToolResponse:
    """Returns the PostgreSQL schema tables and their DDL statements.
    
    Args:
        schema_name: Name of the schema to get DDLs for. Required parameter.
    
    Returns:
        Text content containing the DDL statements for all tables in the schema
    """
    db_url = get_db_url()
    if not db_url:
        logger.error("PostgreSQL database configuration not found")
        return [types.TextContent(
            type="text", 
            text="Error: PostgreSQL database configuration not found in config.yaml. Please add a valid configuration."
        )]
    
    # Check if schema_name is provided
    if not schema_name:
        logger.error("Missing required parameter: schema_name")
        return [types.TextContent(
            type="text",
            text="Error: schema_name is a required parameter. Please specify the schema name."
        )]
    
    try:
        # Handle 'postgres://' vs 'postgresql://' protocol conversion
        if db_url.startswith('postgres://'):
            logger.info("Converting 'postgres://' to 'postgresql://' for psycopg2 compatibility")
            db_url = 'postgresql://' + db_url[len('postgres://'):]
        
        # Connect to the database
        logger.info(f"Connecting to PostgreSQL database to fetch DDLs...")
        conn = psycopg2.connect(db_url)
        
        # Get the DDL statements for all tables in the schema
        logger.info(f"Fetching DDLs for schema: {schema_name}")
        ddl_content = await get_schema_ddls(conn, schema_name)
        
        # Close connection
        conn.close()
        
        return [types.TextContent(type="text", text=ddl_content)]
    
    except Exception as e:
        logger.error(f"Error fetching schema DDLs: {str(e)}")
        error_msg = f"Error fetching schema DDLs: {e}\n\n"
        error_msg += "Please check your database configuration and ensure the schema exists."
        
        # Print stack trace to help debug connection issues
        logger.error(traceback.format_exc())
        
        return [types.TextContent(type="text", text=error_msg)]


async def get_schema_ddls(conn, schema_name: str) -> str:
    """Get DDL statements for all tables in a specific schema.
    
    Args:
        conn: PostgreSQL connection
        schema_name: Name of the schema
        
    Returns:
        Formatted string with DDL statements for all tables
    """
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    ddl_output = f"-- DDL Statements for Schema: {schema_name}\n\n"
    
    try:
        # Get tables in the schema
        cursor.execute("""
            SELECT table_name, table_type
            FROM information_schema.tables
            WHERE table_schema = %s
              AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """, (schema_name,))
        tables = cursor.fetchall()
        
        if not tables:
            return f"-- No tables found in schema '{schema_name}'\n"
        
        for table_info in tables:
            table_name = table_info[0]
            
            # Generate CREATE TABLE statement
            ddl_output += f"-- Table: {schema_name}.{table_name}\n"
            ddl_output += f"CREATE TABLE {schema_name}.{table_name} (\n"
            
            # Get column information
            cursor.execute("""
                SELECT column_name, data_type, character_maximum_length, 
                       is_nullable, column_default,
                       numeric_precision, numeric_scale
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position
            """, (schema_name, table_name))
            columns = cursor.fetchall()
            
            column_definitions = []
            for column in columns:
                col_name = column[0]
                data_type = column[1]
                char_max_len = column[2]
                is_nullable = column[3]
                default_val = column[4]
                num_precision = column[5]
                num_scale = column[6]
                
                # Format the data type with precision/scale/length as needed
                type_display = data_type
                if data_type in ('character varying', 'character', 'varchar', 'char'):
                    if char_max_len is not None:
                        type_display = f"{data_type}({char_max_len})"
                elif data_type in ('numeric', 'decimal'):
                    if num_precision is not None:
                        if num_scale is not None:
                            type_display = f"{data_type}({num_precision},{num_scale})"
                        else:
                            type_display = f"{data_type}({num_precision})"
                
                nullable = "NULL" if is_nullable == "YES" else "NOT NULL"
                default = f" DEFAULT {default_val}" if default_val else ""
                
                column_definitions.append(f"    {col_name} {type_display} {nullable}{default}")
            
            # Get primary key constraints
            cursor.execute("""
                SELECT kcu.column_name, tc.constraint_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu 
                  ON kcu.constraint_name = tc.constraint_name
                 AND kcu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY'
                  AND tc.table_schema = %s
                  AND tc.table_name = %s
                ORDER BY kcu.ordinal_position
            """, (schema_name, table_name))
            pk_columns = cursor.fetchall()
            
            if pk_columns:
                pk_col_names = [col[0] for col in pk_columns]
                pk_constraint_name = pk_columns[0][1]
                column_definitions.append(f"    CONSTRAINT {pk_constraint_name} PRIMARY KEY ({', '.join(pk_col_names)})")
            
            # Combine all column definitions
            ddl_output += ",\n".join(column_definitions)
            ddl_output += "\n);\n\n"
            
            # Get index statements (excluding primary key index which is created with the table)
            cursor.execute("""
                SELECT
                    i.relname as index_name,
                    pg_get_indexdef(i.oid) as index_def
                FROM
                    pg_class t,
                    pg_class i,
                    pg_index ix,
                    pg_namespace n
                WHERE
                    t.oid = ix.indrelid
                    and i.oid = ix.indexrelid
                    and t.relkind = 'r'
                    and t.relname = %s
                    and n.oid = t.relnamespace
                    and n.nspname = %s
                    and NOT ix.indisprimary
                ORDER BY
                    i.relname;
            """, (table_name, schema_name))
            indexes = cursor.fetchall()
            
            for idx in indexes:
                ddl_output += f"{idx[1]};\n\n"
            
            # Get foreign key constraints
            cursor.execute("""
                SELECT
                    tc.constraint_name,
                    kcu.column_name,
                    ccu.table_schema AS referenced_table_schema,
                    ccu.table_name AS referenced_table_name,
                    ccu.column_name AS referenced_column_name,
                    rc.update_rule,
                    rc.delete_rule
                FROM
                    information_schema.table_constraints AS tc
                    JOIN information_schema.key_column_usage AS kcu
                      ON tc.constraint_name = kcu.constraint_name
                      AND tc.table_schema = kcu.table_schema
                    JOIN information_schema.constraint_column_usage AS ccu
                      ON ccu.constraint_name = tc.constraint_name
                    JOIN information_schema.referential_constraints AS rc
                      ON rc.constraint_name = tc.constraint_name
                WHERE
                    tc.constraint_type = 'FOREIGN KEY'
                    AND tc.table_schema = %s
                    AND tc.table_name = %s;
            """, (schema_name, table_name))
            fks = cursor.fetchall()
            
            # Group foreign keys by constraint name (multi-column FKs)
            fk_constraints = {}
            for fk in fks:
                constraint_name = fk[0]
                if constraint_name not in fk_constraints:
                    fk_constraints[constraint_name] = {
                        'columns': [],
                        'ref_schema': fk[2],
                        'ref_table': fk[3],
                        'ref_columns': [],
                        'update_rule': fk[5],
                        'delete_rule': fk[6]
                    }
                fk_constraints[constraint_name]['columns'].append(fk[1])
                fk_constraints[constraint_name]['ref_columns'].append(fk[4])
            
            for constraint_name, fk_info in fk_constraints.items():
                ddl_output += f"ALTER TABLE {schema_name}.{table_name} ADD CONSTRAINT {constraint_name}\n"
                ddl_output += f"    FOREIGN KEY ({', '.join(fk_info['columns'])})\n"
                ddl_output += f"    REFERENCES {fk_info['ref_schema']}.{fk_info['ref_table']} ({', '.join(fk_info['ref_columns'])})\n"
                
                if fk_info['update_rule'] != 'NO ACTION':
                    ddl_output += f"    ON UPDATE {fk_info['update_rule']}\n"
                if fk_info['delete_rule'] != 'NO ACTION':
                    ddl_output += f"    ON DELETE {fk_info['delete_rule']}\n"
                
                ddl_output += ";\n\n"
            
            # Get table comments if any
            cursor.execute("""
                SELECT obj_description(c.oid)
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relname = %s AND n.nspname = %s
            """, (table_name, schema_name))
            comment = cursor.fetchone()
            
            if comment and comment[0]:
                # Fixed the escaping in the comment string
                comment_text = comment[0].replace("'", "''")
                ddl_output += f"COMMENT ON TABLE {schema_name}.{table_name} IS '{comment_text}';  -- Escape single quotes\n\n"
            
            # Add a separator between tables
            ddl_output += "-- --------------------------------------------------------\n\n"
    
    except Exception as e:
        logger.error(f"Error generating DDL statements: {str(e)}")
        ddl_output += f"-- Error generating DDL statements: {str(e)}\n"
        ddl_output += f"-- {traceback.format_exc()}\n"
    
    finally:
        cursor.close()
    
    return ddl_output


async def postgres_query_select(query: str = None) -> ToolResponse:
    """Executes a PostgreSQL SELECT query and returns the results.
    
    Args:
        query: SQL SELECT query to execute. Required parameter.
    
    Returns:
        Text content containing the query results or error message
    """
    db_url = get_db_url()
    if not db_url:
        logger.error("PostgreSQL database configuration not found")
        return [types.TextContent(
            type="text", 
            text="Error: PostgreSQL database configuration not found in config.yaml. Please add a valid configuration."
        )]
    
    # Check if query is provided
    if not query:
        logger.error("Missing required parameter: query")
        return [types.TextContent(
            type="text",
            text="Error: query is a required parameter. Please specify a SELECT query to execute."
        )]
    
    # Validate that the query is a SELECT query (basic security check)
    # query_lower = query.lower().strip()
    # if not query_lower.startswith('select '):
    #     logger.error("Only SELECT queries are allowed")
    #     return [types.TextContent(
    #         type="text",
    #         text="Error: Only SELECT queries are allowed for security reasons."
    #     )]
    
    try:
        # Handle 'postgres://' vs 'postgresql://' protocol conversion
        if db_url.startswith('postgres://'):
            logger.info("Converting 'postgres://' to 'postgresql://' for psycopg2 compatibility")
            db_url = 'postgresql://' + db_url[len('postgres://'):]
        
        # Connect to the database
        logger.info(f"Connecting to PostgreSQL database to execute query...")
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # Execute the query
        logger.info(f"Executing query: {query}")
        cursor.execute(query)
        
        # Fetch all results
        rows = cursor.fetchall()
        column_names = [desc[0] for desc in cursor.description]
        
        # Format the results
        result_text = f"Query executed successfully. {len(rows)} rows returned.\n\n"
        
        # Add column headers
        result_text += "| " + " | ".join(column_names) + " |\n"
        result_text += "| " + " | ".join(["---" for _ in column_names]) + " |\n"
        
        # Add rows (limit to first 100 rows to avoid huge responses)
        row_limit = 100
        for i, row in enumerate(rows[:row_limit]):
            # Convert row items to strings and handle None values
            row_values = [str(val) if val is not None else "NULL" for val in row]
            result_text += "| " + " | ".join(row_values) + " |\n"
        
        # Add note if rows were truncated
        if len(rows) > row_limit:
            result_text += f"\n*Note: Output truncated. Showing {row_limit} of {len(rows)} rows.*"
        
        # Close cursor and connection
        cursor.close()
        conn.close()
        
        return [types.TextContent(type="text", text=result_text)]
    
    except Exception as e:
        logger.error(f"Error executing query: {str(e)}")
        error_msg = f"Error executing query: {e}\n\n"
        error_msg += "Please check your query syntax and ensure the database connection is working."
        
        # Print stack trace to help debug issues
        logger.error(traceback.format_exc())
        
        return [types.TextContent(type="text", text=error_msg)]


async def mysql_query_select(query: str = None) -> ToolResponse:
    """Executes a MySQL SELECT query and returns the results.
    
    Args:
        query: SQL SELECT query to execute. Required parameter.
    
    Returns:
        Text content containing the query results or error message
    """
    mysql_dsn = get_mysql_dsn()
    if not mysql_dsn:
        logger.error("MySQL database configuration not found")
        return [types.TextContent(
            type="text", 
            text="Error: MySQL database configuration not found in config.yaml. Please add a valid configuration."
        )]
    
    # Check if query is provided
    if not query:
        logger.error("Missing required parameter: query")
        return [types.TextContent(
            type="text",
            text="Error: query is a required parameter. Please specify a SELECT query to execute."
        )]
    
    # Validate that the query is a SELECT query (basic security check)
    query_lower = query.lower().strip()
    if not query_lower.startswith('select '):
        logger.error("Only SELECT queries are allowed")
        return [types.TextContent(
            type="text",
            text="Error: Only SELECT queries are allowed for security reasons."
        )]
    
    try:
        # Parse MySQL DSN
        # Format example: 'root:password@tcp(0.0.0.0:3306)/dbname?charset=utf8&parseTime=True'
        conn_info = {}
        
        # Extract user and password
        auth_part, rest = mysql_dsn.split('@', 1)
        user_pass = auth_part.split(':', 1)
        conn_info['user'] = user_pass[0]
        conn_info['password'] = user_pass[1] if len(user_pass) > 1 else ''
        
        # Extract host and port
        tcp_part, db_part = rest.split('/', 1)
        host_port = tcp_part.replace('tcp(', '').replace(')', '')
        if ':' in host_port:
            host, port = host_port.split(':', 1)
            conn_info['host'] = host
            conn_info['port'] = int(port)
        else:
            conn_info['host'] = host_port
            conn_info['port'] = 3306  # Default MySQL port
        
        # Extract database and parameters
        if '?' in db_part:
            db_name, params = db_part.split('?', 1)
            conn_info['database'] = db_name
            
            # Parse parameters (charset, etc.)
            param_pairs = params.split('&')
            for pair in param_pairs:
                if '=' in pair:
                    key, value = pair.split('=', 1)
                    if key.lower() == 'charset':
                        conn_info['charset'] = value
        else:
            conn_info['database'] = db_part
        
        # Hide password in logs
        masked_dsn = f"{conn_info['user']}:****@tcp({conn_info['host']}:{conn_info['port']})/{conn_info['database']}"
        logger.info(f"Connecting to MySQL database: {masked_dsn}")
        
        # Connect to MySQL
        import pymysql
        connection = pymysql.connect(
            host=conn_info.get('host', 'localhost'),
            user=conn_info.get('user', ''),
            password=conn_info.get('password', ''),
            database=conn_info.get('database', ''),
            port=conn_info.get('port', 3306),
            charset=conn_info.get('charset', 'utf8mb4')
        )
        
        # Execute the query
        logger.info(f"Executing MySQL query: {query}")
        with connection.cursor() as cursor:
            cursor.execute(query)
            
            # Fetch all results
            rows = cursor.fetchall()
            
            # Get column names
            column_names = [column[0] for column in cursor.description]
            
            # Format the results
            result_text = f"Query executed successfully. {len(rows)} rows returned.\n\n"
            
            # Add column headers
            result_text += "| " + " | ".join(column_names) + " |\n"
            result_text += "| " + " | ".join(["---" for _ in column_names]) + " |\n"
            
            # Add rows (limit to first 100 rows to avoid huge responses)
            row_limit = 100
            for i, row in enumerate(rows[:row_limit]):
                # Convert row items to strings and handle None values
                row_values = [str(val) if val is not None else "NULL" for val in row]
                result_text += "| " + " | ".join(row_values) + " |\n"
            
            # Add note if rows were truncated
            if len(rows) > row_limit:
                result_text += f"\n*Note: Output truncated. Showing {row_limit} of {len(rows)} rows.*"
        
        # Close connection
        connection.close()
        logger.info("MySQL connection closed")
        
        return [types.TextContent(type="text", text=result_text)]
    
    except Exception as e:
        logger.error(f"Error executing MySQL query: {str(e)}")
        error_msg = f"Error executing MySQL query: {e}\n\n"
        error_msg += "Please check your query syntax and ensure the MySQL database connection is working."
        
        # Print stack trace to help debug issues
        logger.error(traceback.format_exc())
        
        return [types.TextContent(type="text", text=error_msg)]


async def mysql_schema_ddls(schema_name: str = None) -> ToolResponse:
    """Returns the MySQL schema tables and their DDL statements.
    
    Args:
        schema_name: Name of the schema/database to get DDLs for. Required parameter.
    
    Returns:
        Text content containing the DDL statements for all tables in the schema
    """
    mysql_dsn = get_mysql_dsn()
    if not mysql_dsn:
        logger.error("MySQL database configuration not found")
        return [types.TextContent(
            type="text", 
            text="Error: MySQL database configuration not found in config.yaml. Please add a valid configuration."
        )]
    
    # Check if schema_name is provided
    if not schema_name:
        logger.error("Missing required parameter: schema_name")
        return [types.TextContent(
            type="text",
            text="Error: schema_name is a required parameter. Please specify the schema/database name."
        )]
    
    try:
        # Parse MySQL DSN
        # Format example: 'root:password@tcp(0.0.0.0:3306)/dbname?charset=utf8&parseTime=True'
        conn_info = {}
        
        # Extract user and password
        auth_part, rest = mysql_dsn.split('@', 1)
        user_pass = auth_part.split(':', 1)
        conn_info['user'] = user_pass[0]
        conn_info['password'] = user_pass[1] if len(user_pass) > 1 else ''
        
        # Extract host and port
        tcp_part, db_part = rest.split('/', 1)
        host_port = tcp_part.replace('tcp(', '').replace(')', '')
        if ':' in host_port:
            host, port = host_port.split(':', 1)
            conn_info['host'] = host
            conn_info['port'] = int(port)
        else:
            conn_info['host'] = host_port
            conn_info['port'] = 3306  # Default MySQL port
        
        # Extract database and parameters
        if '?' in db_part:
            db_name, params = db_part.split('?', 1)
            conn_info['database'] = db_name
            
            # Parse parameters (charset, etc.)
            param_pairs = params.split('&')
            for pair in param_pairs:
                if '=' in pair:
                    key, value = pair.split('=', 1)
                    if key.lower() == 'charset':
                        conn_info['charset'] = value
        else:
            conn_info['database'] = db_part
        
        # Hide password in logs
        masked_dsn = f"{conn_info['user']}:****@tcp({conn_info['host']}:{conn_info['port']})/{conn_info['database']}"
        logger.info(f"Connecting to MySQL database: {masked_dsn}")
        
        # Connect to MySQL
        import pymysql
        connection = pymysql.connect(
            host=conn_info.get('host', 'localhost'),
            user=conn_info.get('user', ''),
            password=conn_info.get('password', ''),
            database=conn_info.get('database', ''),
            port=conn_info.get('port', 3306),
            charset=conn_info.get('charset', 'utf8mb4')
        )
        
        # Get the DDL statements for all tables in the schema
        logger.info(f"Fetching DDLs for schema/database: {schema_name}")
        ddl_content = await get_mysql_schema_ddls(connection, schema_name)
        
        # Close connection
        connection.close()
        
        return [types.TextContent(type="text", text=ddl_content)]
    
    except Exception as e:
        logger.error(f"Error fetching MySQL schema DDLs: {str(e)}")
        error_msg = f"Error fetching MySQL schema DDLs: {e}\n\n"
        error_msg += "Please check your database configuration and ensure the schema exists."
        
        # Print stack trace to help debug connection issues
        logger.error(traceback.format_exc())
        
        return [types.TextContent(type="text", text=error_msg)]


async def get_mysql_schema_ddls(conn, schema_name: str) -> str:
    """Get DDL statements for all tables in a specific MySQL schema/database.
    
    Args:
        conn: MySQL connection
        schema_name: Name of the schema/database
        
    Returns:
        Formatted string with DDL statements for all tables
    """
    cursor = conn.cursor()
    ddl_output = f"-- DDL Statements for Schema/Database: {schema_name}\n\n"
    
    try:
        # Get tables in the schema
        cursor.execute(f"""
            SELECT table_name, table_type
            FROM information_schema.tables
            WHERE table_schema = %s
              AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """, (schema_name,))
        tables = cursor.fetchall()
        
        if not tables:
            return f"-- No tables found in schema/database '{schema_name}'\n"
        
        for table_info in tables:
            table_name = table_info[0]
            
            # Get the CREATE TABLE statement directly from MySQL
            cursor.execute(f"SHOW CREATE TABLE `{schema_name}`.`{table_name}`")
            create_table_result = cursor.fetchone()
            
            if create_table_result and len(create_table_result) > 1:
                create_table_stmt = create_table_result[1]
                ddl_output += f"-- Table: {schema_name}.{table_name}\n"
                ddl_output += f"{create_table_stmt};\n\n"
            
            # Get indexes (excluding those already in CREATE TABLE)
            cursor.execute(f"""
                SELECT DISTINCT index_name, index_type, non_unique
                FROM information_schema.statistics
                WHERE table_schema = %s AND table_name = %s
                  AND index_name != 'PRIMARY'
                ORDER BY index_name
            """, (schema_name, table_name))
            indexes = cursor.fetchall()
            
            # We don't need to output these separately as they're included in the SHOW CREATE TABLE output
            
            # Add a separator between tables
            ddl_output += "-- --------------------------------------------------------\n\n"
    
    except Exception as e:
        logger.error(f"Error generating MySQL DDL statements: {str(e)}")
        ddl_output += f"-- Error generating DDL statements: {str(e)}\n"
        ddl_output += f"-- {traceback.format_exc()}\n"
    
    finally:
        cursor.close()
    
    return ddl_output

# Define tool configurations
TOOL_CONFIGS = {
    Command.RANDOM_UINT64: ToolConfig(
        name=Command.RANDOM_UINT64,
        description="Generate a random unsigned 64-bit integer (uint64).",
        handler=generate_random_uint64,
        properties={},
        required=[],
    ),
    Command.POSTGRES_SCHEMAS: ToolConfig(
        name=Command.POSTGRES_SCHEMAS,
        description="Retrieve PostgreSQL database schema information. Connects to the database specified in the DATABASE_URL environment variable. Returns information about the database connection, available schemas, and table structures.",
        handler=postgres_schemas,
        properties={},
        required=[],
    ),
    Command.POSTGRES_SCHEMA_DDLS: ToolConfig(
        name=Command.POSTGRES_SCHEMA_DDLS,
        description="Retrieve PostgreSQL schema tables and their DDL statements. Connect to the database specified in DATABASE_URL environment variable and return all DDL statements for the specified schema. Examples: 'public', 'accounting', 'xmeet'.",
        handler=postgres_schema_ddls,
        properties={"schema_name": {"type": "string", "description": "Name of the schema to get DDLs for (required)"}},
        required=["schema_name"],
    ),
    Command.POSTGRES_QUERY_SELECT: ToolConfig(
        name=Command.POSTGRES_QUERY_SELECT,
        description="Executes a PostgreSQL SELECT query and returns the results. Connect to the database specified in DATABASE_URL environment variable and execute the specified SELECT query. Returns the query results or an error message.",
        handler=postgres_query_select,
        properties={"query": {"type": "string", "description": "SQL SELECT query to execute (required)"}},
        required=["query"],
    ),
    Command.MYSQL_QUERY_SELECT: ToolConfig(
        name=Command.MYSQL_QUERY_SELECT,
        description="Executes a MySQL SELECT query and returns the results. Connect to the MySQL database specified in the config and execute the specified SELECT query. Returns the query results or an error message.",
        handler=mysql_query_select,
        properties={"query": {"type": "string", "description": "SQL SELECT query to execute (required)"}},
        required=["query"],
    ),
    Command.MYSQL_SCHEMA_DDLS: ToolConfig(
        name=Command.MYSQL_SCHEMA_DDLS,
        description="Retrieve MySQL schema tables and their DDL statements. Connect to the MySQL database specified in the config and return all DDL statements for the specified schema/database.",
        handler=mysql_schema_ddls,
        properties={"schema_name": {"type": "string", "description": "Name of the schema/database to get DDLs for (required)"}},
        required=["schema_name"],
    ),
}

class MCPServerWrapper:
    """Wrapper around MCP Server to handle initialization properly."""
    
    def __init__(self, name: str):
        self.app = Server(name)
        self._init_event = asyncio.Event()
        self._init_lock = asyncio.Lock()
        self._initialized = False
        self.config = load_config()
        
        # Register tools and handlers
        self._register_tools()
    
    def _register_tools(self):
        """Register all tool handlers with the server."""
        @self.app.call_tool()
        async def fetch_tool(name: str, arguments: Dict[str, Any]) -> ToolResponse:
            logger.info(f"Fetching tool: {name} with arguments: {arguments}")
            try:
                if name == Command.POSTGRES_SCHEMAS:
                    return await postgres_schemas()
                elif name == Command.RANDOM_UINT64:
                    return await generate_random_uint64()
                elif name == Command.POSTGRES_SCHEMA_DDLS:
                    schema_name = arguments.get("schema_name")
                    # Validate that schema_name is provided
                    if not schema_name:
                        logger.error("Missing required parameter: schema_name")
                        return [types.TextContent(
                            type="text",
                            text="Error: Missing required parameter 'schema_name'. Example values: 'public', 'accounting', 'xmeet'"
                        )]
                    return await postgres_schema_ddls(schema_name)
                elif name == Command.POSTGRES_QUERY_SELECT:
                    query = arguments.get("query")
                    # Validate that query is provided
                    if not query:
                        logger.error("Missing required parameter: query")
                        return [types.TextContent(
                            type="text",
                            text="Error: Missing required parameter 'query'. Please specify a SELECT query to execute."
                        )]
                    return await postgres_query_select(query)
                elif name == Command.MYSQL_QUERY_SELECT:
                    query = arguments.get("query")
                    # Validate that query is provided
                    if not query:
                        logger.error("Missing required parameter: query")
                        return [types.TextContent(
                            type="text",
                            text="Error: Missing required parameter 'query'. Please specify a SELECT query to execute."
                        )]
                    return await mysql_query_select(query)
                elif name == Command.MYSQL_SCHEMA_DDLS:
                    schema_name = arguments.get("schema_name")
                    # Validate that schema_name is provided
                    if not schema_name:
                        logger.error("Missing required parameter: schema_name")
                        return [types.TextContent(
                            type="text",
                            text="Error: Missing required parameter 'schema_name'. Please specify the schema/database name."
                        )]
                    return await mysql_schema_ddls(schema_name)
                else:
                    logger.error(f"Unknown tool: {name}")
                    return [types.TextContent(type="text", text=f"Unknown tool: {name}")]
            except Exception as e:
                logger.error(f"Error executing tool {name}: {str(e)}")
                logger.error(traceback.format_exc())
                return [types.TextContent(type="text", text=f"Error processing tool request: {str(e)}")]

        @self.app.list_tools()
        async def list_tools() -> list[types.Tool]:
            logger.info("Listing available tools")
            tools = [
                types.Tool(
                    name=config.name,
                    description=config.description,
                    inputSchema={
                        "type": "object",
                        "properties": config.properties,
                        "required": config.required,
                    },
                )
                for config in TOOL_CONFIGS.values()
            ]
            tool_names = [tool.name for tool in tools]
            logger.info(f"Returning tools to client: {tool_names}")
            return tools

    async def initialize(self):
        """Initialize the server and all its components."""
        async with self._init_lock:
            if not self._initialized:
                logger.info("Starting server initialization...")
                try:
                    # Check configuration
                    db_url = get_db_url()
                    if db_url:
                        logger.info("Found PostgreSQL database configuration")
                        # Test PostgreSQL connection at startup
                        try:
                            if db_url.startswith('postgres://'):
                                db_url = 'postgresql://' + db_url[len('postgres://'):]
                            conn = psycopg2.connect(db_url)
                            logger.info("Successfully connected to PostgreSQL database")
                            conn.close()
                        except Exception as e:
                            logger.warning(f"Could not connect to PostgreSQL database: {str(e)}")
                    else:
                        logger.warning("PostgreSQL database configuration not found. Postgres schema tool will not work correctly.")
                    
                    mysql_dsn = get_mysql_dsn()
                    if mysql_dsn:
                        logger.info("Found MySQL database configuration")
                        # Test MySQL connection at startup
                        try:
                            # Parse MySQL DSN
                            conn_info = {}
                            
                            # Extract user and password
                            auth_part, rest = mysql_dsn.split('@', 1)
                            user_pass = auth_part.split(':', 1)
                            conn_info['user'] = user_pass[0]
                            conn_info['password'] = user_pass[1] if len(user_pass) > 1 else ''
                            
                            # Extract host and port
                            tcp_part, db_part = rest.split('/', 1)
                            host_port = tcp_part.replace('tcp(', '').replace(')', '')
                            if ':' in host_port:
                                host, port = host_port.split(':', 1)
                                conn_info['host'] = host
                                conn_info['port'] = int(port)
                            else:
                                conn_info['host'] = host_port
                                conn_info['port'] = 3306  # Default MySQL port
                            
                            # Extract database and parameters
                            if '?' in db_part:
                                db_name, params = db_part.split('?', 1)
                                conn_info['database'] = db_name
                                
                                # Parse parameters (charset, etc.)
                                param_pairs = params.split('&')
                                for pair in param_pairs:
                                    if '=' in pair:
                                        key, value = pair.split('=', 1)
                                        if key.lower() == 'charset':
                                            conn_info['charset'] = value
                            else:
                                conn_info['database'] = db_part
                            
                            # Connect to MySQL to verify connection
                            import pymysql
                            connection = pymysql.connect(
                                host=conn_info.get('host', 'localhost'),
                                user=conn_info.get('user', ''),
                                password=conn_info.get('password', ''),
                                database=conn_info.get('database', ''),
                                port=conn_info.get('port', 3306),
                                charset=conn_info.get('charset', 'utf8mb4')
                            )
                            logger.info("Successfully connected to MySQL database")
                            connection.close()
                        except Exception as e:
                            logger.warning(f"Could not connect to MySQL database: {str(e)}")
                    else:
                        logger.warning("MySQL database configuration not found.")
                    
                    # Add any additional initialization steps here
                    
                    self._initialized = True
                    self._init_event.set()
                    logger.info("Server initialization completed successfully")
                except Exception as e:
                    logger.error(f"Server initialization failed: {str(e)}")
                    raise

    async def wait_for_initialization(self):
        """Wait for server initialization to complete."""
        await self._init_event.wait()

    def create_initialization_options(self):
        """Create initialization options for the server."""
        return self.app.create_initialization_options()

    async def run(self, *args, **kwargs):
        """Run the server after ensuring initialization is complete."""
        await self.initialize()
        return await self.app.run(*args, **kwargs)

@click.command()
@click.option("--port", default=5435, help="Port to listen on")
@click.option(
    "--transport",
    type=click.Choice(["http"]),
    default="http",
    help="Transport type (http for streamable HTTP)",
)
def main(port: int, transport: str) -> int:
    # Create wrapped server instance
    app = MCPServerWrapper("mcp-storage")
    logger.info("MCP Storage server created")

    if transport == "http":
        from mcp.server.streamable_http import StreamableHTTPServerTransport
        from starlette.applications import Starlette
        from starlette.routing import Route

        # Create streamable HTTP transport
        http_transport = StreamableHTTPServerTransport(
            mcp_session_id="mcp-storage", is_json_response_enabled=False
        )
        logger.info(f"Starting server with Streamable HTTP transport on port {port}")

        async def handle_http(request):
            """Handle HTTP requests for streamable transport."""
            logger.info(f"HTTP request: {request.method} {request.url.path}")

            try:
                # Ensure initialization is complete before accepting connections
                await app.initialize()

                # Handle the request using the transport
                await http_transport.handle_request(
                    request.scope, request.receive, request._send
                )
            except Exception as e:
                logger.error(f"Error in HTTP handler: {str(e)}")
                logger.error(traceback.format_exc())
                raise

        # Store the app connection task
        app_task = None

        async def startup():
            """Initialize server on startup."""
            nonlocal app_task
            await app.initialize()

            # Connect the transport to the app
            async def run_app():
                async with http_transport.connect() as streams:
                    await app.run(
                        streams[0], streams[1], app.create_initialization_options()
                    )

            app_task = asyncio.create_task(run_app())

        # OAuth endpoints
        async def health_check(request):
            """Simple health check endpoint."""
            from starlette.responses import JSONResponse

            return JSONResponse({"status": "healthy", "service": "mcp-storage"})

        async def handle_register(request):
            """Handle OAuth dynamic client registration."""
            from starlette.responses import JSONResponse

            # Return a mock registration response for Claude Code
            return JSONResponse(
                {
                    "client_id": "mcp-storage-client",
                    "client_secret": "not-used",
                    "registration_access_token": "not-used",
                    "registration_client_uri": f"http://localhost:{port}/register/mcp-storage-client",
                    "grant_types": ["implicit", "authorization_code"],
                    "response_types": ["token", "code"],
                    "redirect_uris": [f"http://localhost:{port}/callback"],
                    "application_type": "web",
                    "token_endpoint_auth_method": "none",
                }
            )

        async def handle_oauth_metadata(request):
            """Handle OAuth authorization server metadata request."""
            from starlette.responses import JSONResponse

            return JSONResponse(
                {
                    "issuer": f"http://localhost:{port}",
                    "authorization_endpoint": f"http://localhost:{port}/authorize",
                    "token_endpoint": f"http://localhost:{port}/token",
                    "registration_endpoint": f"http://localhost:{port}/register",
                    "response_types_supported": ["code", "token"],
                    "grant_types_supported": ["authorization_code", "implicit"],
                    "token_endpoint_auth_methods_supported": [
                        "none",
                        "client_secret_post",
                    ],
                    "code_challenge_methods_supported": ["S256", "plain"],
                }
            )

        async def handle_authorize(request):
            """Handle OAuth authorization requests."""
            import secrets

            from starlette.responses import RedirectResponse

            # Extract query parameters
            client_id = request.query_params.get("client_id")
            redirect_uri = request.query_params.get(
                "redirect_uri", f"http://localhost:{port}/callback"
            )
            state = request.query_params.get("state", "")

            # PKCE parameters
            code_challenge = request.query_params.get("code_challenge")  # noqa: F841
            code_challenge_method = request.query_params.get(
                "code_challenge_method", "plain"
            )

            # Generate a mock authorization code
            code = secrets.token_urlsafe(32)

            # Log the authorization request
            logger.info(
                f"Authorization request from client: {client_id}, "
                f"PKCE method: {code_challenge_method}"
            )

            # Redirect back with the authorization code
            redirect_url = f"{redirect_uri}?code={code}&state={state}"
            return RedirectResponse(url=redirect_url)

        async def handle_token(request):
            """Handle OAuth token exchange requests."""
            import secrets

            from starlette.responses import JSONResponse

            # Parse form data
            form_data = await request.form()
            grant_type = form_data.get("grant_type")
            code_verifier = form_data.get("code_verifier")

            logger.info(
                f"Token request with grant_type: {grant_type}, "
                f"has_verifier: {bool(code_verifier)}"
            )

            # Generate a mock access token
            access_token = secrets.token_urlsafe(32)

            return JSONResponse(
                {
                    "access_token": access_token,
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "scope": "read write",
                }
            )

        starlette_app = Starlette(
            debug=True,
            routes=[
                Route("/", endpoint=handle_http, methods=["GET", "POST"]),
                Route("/health", endpoint=health_check, methods=["GET"]),
                Route(
                    "/.well-known/oauth-authorization-server",
                    endpoint=handle_oauth_metadata,
                    methods=["GET"],
                ),
                Route("/register", endpoint=handle_register, methods=["POST"]),
                Route("/authorize", endpoint=handle_authorize, methods=["GET"]),
                Route("/token", endpoint=handle_token, methods=["POST"]),
            ],
            on_startup=[startup],
        )

        import uvicorn

        logger.info("Starting uvicorn server for Streamable HTTP...")
        uvicorn.run(starlette_app, host="0.0.0.0", port=port)

    return 0
