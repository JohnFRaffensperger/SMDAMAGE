#!/usr/bin/env python3
"""
Made by Claude. Interactive SQLite Database Explorer for SMDAMAGE Data
Provides a simple command-line interface to explore the database
"""

import sqlite3
import sys
import os

DB_NAME = "smdamage_data.db"

class DatabaseExplorer:
    """Interactive database explorer"""
    
    def __init__(self):
        if not os.path.exists(DB_NAME):
            print(f"❌ Database '{DB_NAME}' not found.")
            print("Run 'python create_database.py' first to create the database.")
            sys.exit(1)
        
        self.conn = sqlite3.connect(DB_NAME)
        self.cursor = self.conn.cursor()
        
    def show_tables(self):
        """Show all tables in the database"""
        self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in self.cursor.fetchall() if row[0] != 'sqlite_sequence']
        
        print("\n📊 Available Tables:")
        print("-" * 40)
        for i, table in enumerate(tables, 1):
            self.cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = self.cursor.fetchone()[0]
            print(f"{i:2}. {table:<25} ({count:>4} records)")
        
        return tables
    
    def show_table_schema(self, table_name):
        """Show schema for a specific table"""
        try:
            self.cursor.execute(f"PRAGMA table_info({table_name})")
            columns = self.cursor.fetchall()
            
            print(f"\n🏗️  Schema for '{table_name}':")
            print("-" * 50)
            print("Column Name                Type        Null?  Key")
            print("-" * 50)
            for col in columns:
                col_id, name, col_type, not_null, default_val, primary_key = col
                null_str = "NO" if not_null else "YES"
                key_str = "PK" if primary_key else ""
                print(f"{name:<25} {col_type:<10} {null_str:<6} {key_str}")
        
        except sqlite3.Error as e:
            print(f"❌ Error: {e}")
    
    def preview_table(self, table_name, limit=10):
        """Show sample data from a table"""
        try:
            self.cursor.execute(f"SELECT * FROM {table_name} LIMIT {limit}")
            rows = self.cursor.fetchall()
            
            # Get column names
            self.cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [col[1] for col in self.cursor.fetchall()]
            
            print(f"\n👁️  Preview of '{table_name}' (first {limit} rows):")
            print("-" * 80)
            
            # Print header
            header = " | ".join(f"{col[:12]:<12}" for col in columns)
            print(header)
            print("-" * len(header))
            
            # Print data rows
            for row in rows:
                row_str = " | ".join(f"{str(val)[:12]:<12}" for val in row)
                print(row_str)
                
            if len(rows) == 0:
                print("No data found.")
        
        except sqlite3.Error as e:
            print(f"❌ Error: {e}")
    
    def run_custom_query(self, query):
        """Execute a custom SQL query"""
        try:
            self.cursor.execute(query)
            rows = self.cursor.fetchall()
            
            print(f"\n🔍 Query Results:")
            print("-" * 50)
            
            if rows:
                # Print column names if available
                if self.cursor.description:
                    columns = [desc[0] for desc in self.cursor.description]
                    header = " | ".join(f"{col[:15]:<15}" for col in columns)
                    print(header)
                    print("-" * len(header))
                
                # Print data
                for row in rows:
                    row_str = " | ".join(f"{str(val)[:15]:<15}" for val in row)
                    print(row_str)
                
                print(f"\n({len(rows)} rows returned)")
            else:
                print("No results returned.")
        
        except sqlite3.Error as e:
            print(f"❌ SQL Error: {e}")
    
    def show_sample_queries(self):
        """Show sample queries for users to try"""
        queries = [
            ("Agriculture bids over $20", 
             "SELECT price_usd2022, quantity_mgtons_c FROM agriculture_bids WHERE price_usd2022 > 20"),
            
            ("Top 5 most expensive carbon bids", 
             "SELECT price_per_ton_c, quantity_mtons_c FROM carbon_bids ORDER BY price_per_ton_c DESC LIMIT 5"),
            
            ("Chemical pulse data summary", 
             "SELECT hector_name, emission_factor, hector_units FROM warming_factors ORDER BY hector_name"),
            
            ("Forestry removal for year 10", 
             "SELECT * FROM forestry_removal WHERE year = 10"),
            
            ("Bid step statistics for CH4", 
             "SELECT COUNT(*), MIN(price_per_mton), MAX(price_per_mton), AVG(price_per_mton) FROM ch4_bids"),
        ]
        
        print("\n💡 Sample Queries:")
        print("-" * 60)
        for i, (description, query) in enumerate(queries, 1):
            print(f"\n{i}. {description}")
            print(f"   {query}")
        
        return queries
    
    def interactive_mode(self):
        """Run interactive exploration mode"""
        print("🗄️  SMDAMAGE Database Explorer")
        print("=" * 50)
        print("Commands:")
        print("  'tables' - Show all tables")
        print("  'schema <table>' - Show table schema") 
        print("  'preview <table>' - Show sample data")
        print("  'samples' - Show sample queries")
        print("  'query <sql>' - Run custom SQL query")
        print("  'help' - Show this help")
        print("  'quit' - Exit")
        print("=" * 50)
        
        while True:
            try:
                command = input("\n🔍 Enter command: ").strip()
                
                if not command:
                    continue
                    
                if command.lower() in ['quit', 'exit', 'q']:
                    break
                
                elif command.lower() == 'help':
                    print("\nCommands:")
                    print("  tables - Show all tables")
                    print("  schema <table> - Show table schema")
                    print("  preview <table> - Show sample data")
                    print("  samples - Show sample queries")
                    print("  query <sql> - Run custom SQL query")
                
                elif command.lower() == 'tables':
                    self.show_tables()
                
                elif command.lower() == 'samples':
                    self.show_sample_queries()
                
                elif command.lower().startswith('schema '):
                    table = command[7:].strip()
                    self.show_table_schema(table)
                
                elif command.lower().startswith('preview '):
                    table = command[8:].strip()
                    self.preview_table(table)
                
                elif command.lower().startswith('query '):
                    sql = command[6:].strip()
                    self.run_custom_query(sql)
                
                else:
                    print("❓ Unknown command. Type 'help' for available commands.")
            
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
        
        self.conn.close()

def main():
    """Main entry point"""
    if len(sys.argv) > 1:
        # Command line mode
        explorer = DatabaseExplorer()
        
        if sys.argv[1] == 'tables':
            explorer.show_tables()
        
        elif sys.argv[1] == 'schema' and len(sys.argv) > 2:
            explorer.show_table_schema(sys.argv[2])
        
        elif sys.argv[1] == 'preview' and len(sys.argv) > 2:
            explorer.preview_table(sys.argv[2])
        
        elif sys.argv[1] == 'samples':
            explorer.show_sample_queries()
        
        else:
            print("Usage:")
            print("  python query_tool.py                    # Interactive mode")
            print("  python query_tool.py tables             # Show tables")
            print("  python query_tool.py schema <table>     # Show schema")
            print("  python query_tool.py preview <table>    # Preview data")
            print("  python query_tool.py samples            # Sample queries")
        
        explorer.conn.close()
    
    else:
        # Interactive mode
        explorer = DatabaseExplorer()
        explorer.interactive_mode()

if __name__ == "__main__":
    main()