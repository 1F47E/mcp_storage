#!/usr/bin/env python3
"""
MCP Storage Server Test Client

Tests all endpoints and tools of the MCP Storage Server using HTTP transport.
"""

import json
import sys
import time
import requests
import argparse
from typing import Dict, Any, Optional


class MCPTestClient:
    def __init__(self, base_url: str, debug: bool = False):
        self.base_url = base_url.rstrip('/')
        self.debug = debug
        self.session_id = None
        self.request_id = 0
        
    def _next_id(self) -> int:
        """Get next request ID"""
        self.request_id += 1
        return self.request_id
        
    def _log(self, message: str, data: Any = None):
        """Log debug messages"""
        if self.debug:
            print(f"[DEBUG] {message}")
            if data is not None:
                print(json.dumps(data, indent=2))
                
    def _make_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a JSON-RPC request"""
        request_id = self._next_id()
        
        # Build request
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
        }
        
        if params is not None:
            request["params"] = params
            
        self._log(f"Request to {method}:", request)
        
        # Make HTTP request
        headers = {
            "Content-Type": "application/json",
        }
        
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
            
        try:
            response = requests.post(
                self.base_url,
                json=request,
                headers=headers
            )
            response.raise_for_status()
            
            # Check for session ID in response
            if "Mcp-Session-Id" in response.headers:
                self.session_id = response.headers["Mcp-Session-Id"]
                self._log(f"Session ID received: {self.session_id}")
                
            # Parse response
            if response.text:
                result = response.json()
                self._log(f"Response from {method}:", result)
                return result
            else:
                self._log(f"Empty response from {method}")
                return None
                
        except Exception as e:
            print(f"Request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            raise
            
    def send_notification(self, method: str, params: Optional[Dict[str, Any]] = None):
        """Send a JSON-RPC notification (no ID)"""
        request = {
            "jsonrpc": "2.0",
            "method": method,
        }
        
        if params is not None:
            request["params"] = params
            
        self._log(f"Notification to {method}:", request)
        
        headers = {
            "Content-Type": "application/json",
        }
        
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
            
        try:
            response = requests.post(
                self.base_url,
                json=request,
                headers=headers
            )
            response.raise_for_status()
            self._log(f"Notification sent successfully")
        except Exception as e:
            print(f"Notification failed: {e}")
            raise
            
    def test_health(self) -> bool:
        """Test health endpoint"""
        print("\n=== Testing Health Endpoint ===")
        try:
            response = requests.get(f"{self.base_url}/health")
            response.raise_for_status()
            data = response.json()
            print(f"✓ Health check passed: {data}")
            return True
        except Exception as e:
            print(f"✗ Health check failed: {e}")
            return False
            
    def test_initialize(self) -> bool:
        """Test initialize method"""
        print("\n=== Testing Initialize ===")
        try:
            response = self._make_request("initialize", {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {
                    "name": "MCP Test Client",
                    "version": "1.0.0"
                }
            })
            
            if "error" in response:
                print(f"✗ Initialize failed: {response['error']}")
                return False
                
            print(f"✓ Initialize successful")
            print(f"  Server: {response['result']['serverInfo']}")
            print(f"  Capabilities: {response['result']['capabilities']}")
            
            # Send initialized notification
            self.send_notification("notifications/initialized")
            
            return True
        except Exception as e:
            print(f"✗ Initialize failed: {e}")
            return False
            
    def test_list_tools(self) -> Optional[list]:
        """Test tools/list method"""
        print("\n=== Testing List Tools ===")
        try:
            response = self._make_request("tools/list")
            
            if "error" in response:
                print(f"✗ List tools failed: {response['error']}")
                return None
                
            tools = response['result']['tools']
            print(f"✓ Found {len(tools)} tools:")
            for tool in tools:
                print(f"  - {tool['name']}: {tool['description']}")
                
            return tools
        except Exception as e:
            print(f"✗ List tools failed: {e}")
            return None
            
    def test_tool(self, tool_name: str, arguments: Dict[str, Any] = None) -> bool:
        """Test a specific tool"""
        print(f"\n=== Testing Tool: {tool_name} ===")
        try:
            response = self._make_request("tools/call", {
                "name": tool_name,
                "arguments": arguments or {}
            })
            
            if "error" in response:
                print(f"✗ Tool call failed: {response['error']}")
                return False
                
            result = response['result']
            if result.get('isError'):
                print(f"✗ Tool returned error: {result['content'][0]['text']}")
                return False
                
            print(f"✓ Tool call successful")
            for content in result['content']:
                if content['type'] == 'text':
                    # Try to parse as JSON for better display
                    try:
                        data = json.loads(content['text'])
                        print(f"  Result: {json.dumps(data, indent=2)}")
                    except:
                        print(f"  Result: {content['text']}")
                        
            return True
        except Exception as e:
            print(f"✗ Tool call failed: {e}")
            return False
            
    def run_all_tests(self) -> Dict[str, bool]:
        """Run all tests"""
        results = {}
        
        # Test health
        results['health'] = self.test_health()
        
        # Test initialize
        results['initialize'] = self.test_initialize()
        if not results['initialize']:
            print("\n✗ Cannot continue without successful initialization")
            return results
            
        # Test list tools
        tools = self.test_list_tools()
        results['list_tools'] = tools is not None
        
        if tools:
            # Test each tool
            for tool in tools:
                tool_name = tool['name']
                
                if tool_name == "random_uint64":
                    results[tool_name] = self.test_tool(tool_name)
                    
                elif tool_name == "postgres_schemas":
                    results[tool_name] = self.test_tool(tool_name)
                    
                elif tool_name == "postgres_schema_ddls":
                    # Skip if no schemas available
                    print(f"\n=== Skipping {tool_name} (requires schema name) ===")
                    
                elif tool_name == "postgres_query_select":
                    results[tool_name] = self.test_tool(tool_name, {
                        "query": "SELECT version()"
                    })
                    
                elif tool_name == "mysql_query_select":
                    results[tool_name] = self.test_tool(tool_name, {
                        "query": "SELECT VERSION()"
                    })
                    
                elif tool_name == "mysql_schema_ddls":
                    # Skip if no schemas available
                    print(f"\n=== Skipping {tool_name} (requires schema name) ===")
                    
        return results
        

def main():
    parser = argparse.ArgumentParser(description='Test MCP Storage Server')
    parser.add_argument('--host', default='localhost', help='Server host')
    parser.add_argument('--port', default='5435', help='Server port')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    parser.add_argument('--tool', help='Test specific tool')
    parser.add_argument('--args', help='Tool arguments as JSON')
    
    args = parser.parse_args()
    
    base_url = f"http://{args.host}:{args.port}/"
    client = MCPTestClient(base_url, debug=args.debug)
    
    print(f"Testing MCP Storage Server at {base_url}")
    
    if args.tool:
        # Test specific tool
        if not client.test_initialize():
            sys.exit(1)
            
        arguments = {}
        if args.args:
            try:
                arguments = json.loads(args.args)
            except:
                print(f"Invalid JSON arguments: {args.args}")
                sys.exit(1)
                
        success = client.test_tool(args.tool, arguments)
        sys.exit(0 if success else 1)
    else:
        # Run all tests
        results = client.run_all_tests()
        
        # Summary
        print("\n=== Test Summary ===")
        passed = sum(1 for v in results.values() if v)
        total = len(results)
        
        for test, result in results.items():
            status = "✓" if result else "✗"
            print(f"{status} {test}")
            
        print(f"\nPassed: {passed}/{total}")
        
        # Exit with error if any tests failed
        sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()