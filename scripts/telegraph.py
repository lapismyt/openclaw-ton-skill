#!/usr/bin/env python3
"""
Telegraph Publishing CLI

Publish markdown content to telegra.ph.

Commands:
  create-account  Create a Telegraph account
  publish         Publish markdown file to Telegraph
  edit            Edit existing Telegraph page
  list            List created pages

Example:
  python telegraph.py create-account --short-name "MyBot" --author-name "AI Assistant"
  python telegraph.py publish --file doc.md --title "My Article"
  python telegraph.py edit --url "https://telegra.ph/My-Article-01-01" --file updated.md
  python telegraph.py list --limit 10
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import requests

# =============================================================================
# Constants
# =============================================================================

TELEGRAPH_API = "https://api.telegra.ph"
CONFIG_DIR = Path.home() / ".openclaw" / "ton-skill"
CONFIG_FILE = CONFIG_DIR / "config.json"
MAX_CONTENT_SIZE = 64 * 1024  # 64KB limit for Telegraph content


# =============================================================================
# Config Management
# =============================================================================


def load_config() -> Dict[str, Any]:
    """Load config from file."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}


def save_config(config: Dict[str, Any]) -> None:
    """Save config to file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def get_telegraph_token() -> Optional[str]:
    """Get Telegraph access token from config."""
    config = load_config()
    return config.get("telegraph_token")


def set_telegraph_token(token: str) -> None:
    """Save Telegraph access token to config."""
    config = load_config()
    config["telegraph_token"] = token
    save_config(config)


# =============================================================================
# Telegraph API
# =============================================================================


def api_request(method: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Make Telegraph API request."""
    url = f"{TELEGRAPH_API}/{method}"
    
    try:
        response = requests.post(url, json=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if not data.get("ok"):
            error = data.get("error", "Unknown error")
            return {"success": False, "error": f"Telegraph API error: {error}"}
        
        return {"success": True, "result": data.get("result")}
    
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": f"Request failed: {e}"}
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"Invalid JSON response: {e}"}


def create_account(short_name: str, author_name: Optional[str] = None, 
                   author_url: Optional[str] = None) -> Dict[str, Any]:
    """Create Telegraph account."""
    params = {"short_name": short_name}
    if author_name:
        params["author_name"] = author_name
    if author_url:
        params["author_url"] = author_url
    
    return api_request("createAccount", params)


def create_page(access_token: str, title: str, content: List[Any],
                author_name: Optional[str] = None, 
                author_url: Optional[str] = None,
                return_content: bool = False) -> Dict[str, Any]:
    """Create Telegraph page."""
    params = {
        "access_token": access_token,
        "title": title,
        "content": content,
        "return_content": return_content
    }
    if author_name:
        params["author_name"] = author_name
    if author_url:
        params["author_url"] = author_url
    
    return api_request("createPage", params)


def edit_page(access_token: str, path: str, title: str, content: List[Any],
              author_name: Optional[str] = None,
              author_url: Optional[str] = None,
              return_content: bool = False) -> Dict[str, Any]:
    """Edit existing Telegraph page."""
    params = {
        "access_token": access_token,
        "path": path,
        "title": title,
        "content": content,
        "return_content": return_content
    }
    if author_name:
        params["author_name"] = author_name
    if author_url:
        params["author_url"] = author_url
    
    return api_request("editPage", params)


def get_page_list(access_token: str, offset: int = 0, 
                  limit: int = 50) -> Dict[str, Any]:
    """Get list of pages created by account."""
    params = {
        "access_token": access_token,
        "offset": offset,
        "limit": min(limit, 200)  # API max is 200
    }
    return api_request("getPageList", params)


def get_page(path: str, return_content: bool = True) -> Dict[str, Any]:
    """Get page by path."""
    params = {"path": path, "return_content": return_content}
    return api_request("getPage", params)


# =============================================================================
# Markdown to Telegraph Nodes Converter
# =============================================================================


class MarkdownToTelegraphConverter:
    """
    Convert Markdown to Telegraph Node format.
    
    Supported elements:
    - Headings (h3, h4)
    - Paragraphs
    - Bold (**text** or __text__)
    - Italic (*text* or _text_)
    - Code (`code` and ```code blocks```)
    - Links [text](url)
    - Images ![alt](url)
    - Lists (- or * or 1.)
    - Blockquotes (>)
    - Horizontal rules (---)
    - Tables (converted to lists)
    """
    
    def __init__(self):
        self.nodes: List[Any] = []
    
    def convert(self, markdown: str) -> List[Any]:
        """Convert markdown string to Telegraph nodes."""
        self.nodes = []
        
        # Normalize line endings
        markdown = markdown.replace("\r\n", "\n").replace("\r", "\n")
        
        # Split into blocks
        blocks = self._split_blocks(markdown)
        
        for block in blocks:
            if not block.strip():
                continue
            self._process_block(block)
        
        return self.nodes
    
    def _split_blocks(self, text: str) -> List[str]:
        """Split text into blocks (paragraphs, code blocks, etc.)."""
        blocks = []
        current_block = []
        in_code_block = False
        code_fence = ""
        
        lines = text.split("\n")
        
        for line in lines:
            # Check for code fence
            fence_match = re.match(r'^(`{3,}|~{3,})(\w*)?$', line.strip())
            
            if fence_match and not in_code_block:
                # Start code block
                if current_block:
                    blocks.append("\n".join(current_block))
                    current_block = []
                in_code_block = True
                code_fence = fence_match.group(1)[0]
                current_block.append(line)
            elif in_code_block:
                current_block.append(line)
                # Check for end of code block
                if line.strip().startswith(code_fence * 3) and line.strip() == code_fence * len(line.strip()):
                    if re.match(rf'^{code_fence}{{3,}}$', line.strip()):
                        blocks.append("\n".join(current_block))
                        current_block = []
                        in_code_block = False
            elif line.strip() == "":
                if current_block:
                    blocks.append("\n".join(current_block))
                    current_block = []
            else:
                current_block.append(line)
        
        if current_block:
            blocks.append("\n".join(current_block))
        
        return blocks
    
    def _process_block(self, block: str) -> None:
        """Process a single block."""
        lines = block.split("\n")
        first_line = lines[0].strip()
        
        # Code block (fenced)
        if first_line.startswith("```") or first_line.startswith("~~~"):
            self._process_code_block(block)
            return
        
        # Heading
        if first_line.startswith("#"):
            self._process_heading(first_line)
            return
        
        # Horizontal rule
        if re.match(r'^[-*_]{3,}$', first_line):
            self.nodes.append({"tag": "hr"})
            return
        
        # Blockquote
        if first_line.startswith(">"):
            self._process_blockquote(block)
            return
        
        # List
        if re.match(r'^[\-\*\+]\s', first_line) or re.match(r'^\d+\.\s', first_line):
            self._process_list(block)
            return
        
        # Table (convert to list)
        if "|" in first_line and len(lines) > 1:
            if re.match(r'^\|?[\s\-:]+\|', lines[1] if len(lines) > 1 else ""):
                self._process_table(block)
                return
        
        # Regular paragraph
        self._process_paragraph(block)
    
    def _process_heading(self, line: str) -> None:
        """Process heading (# ## ### etc.)."""
        match = re.match(r'^(#{1,6})\s+(.+)$', line)
        if match:
            level = len(match.group(1))
            text = match.group(2).strip()
            # Telegraph only supports h3 and h4
            tag = "h3" if level <= 2 else "h4"
            children = self._parse_inline(text)
            self.nodes.append({"tag": tag, "children": children})
    
    def _process_code_block(self, block: str) -> None:
        """Process fenced code block."""
        lines = block.split("\n")
        # Remove fence lines
        if lines[0].strip().startswith("```") or lines[0].strip().startswith("~~~"):
            lines = lines[1:]
        if lines and (lines[-1].strip().startswith("```") or lines[-1].strip().startswith("~~~")):
            lines = lines[:-1]
        
        code_text = "\n".join(lines)
        if code_text:
            self.nodes.append({"tag": "pre", "children": [code_text]})
    
    def _process_blockquote(self, block: str) -> None:
        """Process blockquote."""
        lines = block.split("\n")
        text_lines = []
        for line in lines:
            # Remove > prefix
            stripped = re.sub(r'^>\s?', '', line)
            text_lines.append(stripped)
        
        text = " ".join(text_lines).strip()
        children = self._parse_inline(text)
        self.nodes.append({"tag": "blockquote", "children": children})
    
    def _process_list(self, block: str) -> None:
        """Process ordered or unordered list."""
        lines = block.split("\n")
        
        # Detect list type
        is_ordered = bool(re.match(r'^\d+\.\s', lines[0].strip()))
        tag = "ol" if is_ordered else "ul"
        
        items = []
        current_item = []
        
        for line in lines:
            # Check if new list item
            if re.match(r'^[\-\*\+]\s', line.strip()) or re.match(r'^\d+\.\s', line.strip()):
                if current_item:
                    items.append(" ".join(current_item))
                # Remove list marker
                text = re.sub(r'^[\-\*\+]\s', '', line.strip())
                text = re.sub(r'^\d+\.\s', '', text)
                current_item = [text]
            else:
                # Continuation of current item
                current_item.append(line.strip())
        
        if current_item:
            items.append(" ".join(current_item))
        
        # Build list node
        children = []
        for item in items:
            item_children = self._parse_inline(item)
            children.append({"tag": "li", "children": item_children})
        
        self.nodes.append({"tag": tag, "children": children})
    
    def _process_table(self, block: str) -> None:
        """Convert table to list (Telegraph doesn't support tables)."""
        lines = block.split("\n")
        
        # Parse header
        header_cells = self._parse_table_row(lines[0])
        
        # Skip separator line (index 1)
        
        # Parse data rows
        data_rows = []
        for line in lines[2:]:
            if line.strip():
                data_rows.append(self._parse_table_row(line))
        
        # Convert to list representation
        if header_cells:
            # Add header as bold text
            header_text = " | ".join(header_cells)
            self.nodes.append({"tag": "p", "children": [
                {"tag": "b", "children": [header_text]}
            ]})
        
        # Add data rows as list
        if data_rows:
            items = []
            for row in data_rows:
                row_text = " | ".join(row)
                items.append({"tag": "li", "children": self._parse_inline(row_text)})
            self.nodes.append({"tag": "ul", "children": items})
    
    def _parse_table_row(self, line: str) -> List[str]:
        """Parse a table row into cells."""
        # Remove leading/trailing pipes
        line = line.strip()
        if line.startswith("|"):
            line = line[1:]
        if line.endswith("|"):
            line = line[:-1]
        
        cells = [cell.strip() for cell in line.split("|")]
        return cells
    
    def _process_paragraph(self, block: str) -> None:
        """Process regular paragraph."""
        # Join lines with space
        text = " ".join(line.strip() for line in block.split("\n"))
        text = text.strip()
        
        if not text:
            return
        
        children = self._parse_inline(text)
        self.nodes.append({"tag": "p", "children": children})
    
    def _parse_inline(self, text: str) -> List[Any]:
        """Parse inline elements (bold, italic, code, links, images)."""
        result: List[Any] = []
        
        # Regex patterns for inline elements
        patterns = [
            # Image: ![alt](url)
            (r'!\[([^\]]*)\]\(([^)]+)\)', self._handle_image),
            # Link: [text](url)
            (r'\[([^\]]+)\]\(([^)]+)\)', self._handle_link),
            # Bold: **text** or __text__
            (r'\*\*([^*]+)\*\*', self._handle_bold),
            (r'__([^_]+)__', self._handle_bold),
            # Italic: *text* or _text_ (not inside words)
            (r'(?<![*\w])\*([^*]+)\*(?![*\w])', self._handle_italic),
            (r'(?<![_\w])_([^_]+)_(?![_\w])', self._handle_italic),
            # Inline code: `code`
            (r'`([^`]+)`', self._handle_code),
        ]
        
        # Process text by finding and replacing patterns
        remaining = text
        
        while remaining:
            earliest_match = None
            earliest_pos = len(remaining)
            matched_handler = None
            
            for pattern, handler in patterns:
                match = re.search(pattern, remaining)
                if match and match.start() < earliest_pos:
                    earliest_match = match
                    earliest_pos = match.start()
                    matched_handler = handler
            
            if earliest_match and matched_handler:
                # Add text before match
                if earliest_pos > 0:
                    result.append(remaining[:earliest_pos])
                
                # Add matched element
                element = matched_handler(earliest_match)
                result.append(element)
                
                # Continue with remaining text
                remaining = remaining[earliest_match.end():]
            else:
                # No more matches, add remaining text
                if remaining:
                    result.append(remaining)
                break
        
        # Clean up result - merge adjacent strings
        cleaned = []
        for item in result:
            if isinstance(item, str):
                if cleaned and isinstance(cleaned[-1], str):
                    cleaned[-1] += item
                elif item:  # Don't add empty strings
                    cleaned.append(item)
            else:
                cleaned.append(item)
        
        return cleaned if cleaned else [""]
    
    def _handle_image(self, match: re.Match) -> Dict[str, Any]:
        """Handle image match."""
        alt = match.group(1)
        url = match.group(2)
        node: Dict[str, Any] = {"tag": "img", "attrs": {"src": url}}
        if alt:
            node["attrs"]["alt"] = alt
        return node
    
    def _handle_link(self, match: re.Match) -> Dict[str, Any]:
        """Handle link match."""
        text = match.group(1)
        url = match.group(2)
        return {"tag": "a", "attrs": {"href": url}, "children": [text]}
    
    def _handle_bold(self, match: re.Match) -> Dict[str, Any]:
        """Handle bold match."""
        text = match.group(1)
        # Recursively parse for nested inline elements
        children = self._parse_inline(text)
        return {"tag": "b", "children": children}
    
    def _handle_italic(self, match: re.Match) -> Dict[str, Any]:
        """Handle italic match."""
        text = match.group(1)
        children = self._parse_inline(text)
        return {"tag": "i", "children": children}
    
    def _handle_code(self, match: re.Match) -> Dict[str, Any]:
        """Handle inline code match."""
        code = match.group(1)
        return {"tag": "code", "children": [code]}


def markdown_to_nodes(markdown: str) -> List[Any]:
    """Convert markdown to Telegraph nodes."""
    converter = MarkdownToTelegraphConverter()
    return converter.convert(markdown)


# =============================================================================
# Content Splitting for Large Documents
# =============================================================================


def estimate_content_size(content: List[Any]) -> int:
    """Estimate JSON size of content."""
    return len(json.dumps(content, ensure_ascii=False).encode("utf-8"))


def split_content_for_publishing(content: List[Any], 
                                  max_size: int = MAX_CONTENT_SIZE) -> List[List[Any]]:
    """
    Split content into parts if it exceeds max size.
    
    Returns list of content parts, each under max_size.
    """
    total_size = estimate_content_size(content)
    
    if total_size <= max_size:
        return [content]
    
    # Need to split
    parts = []
    current_part: List[Any] = []
    current_size = 2  # Account for [] brackets
    
    for node in content:
        node_size = len(json.dumps(node, ensure_ascii=False).encode("utf-8")) + 1  # +1 for comma
        
        if current_size + node_size > max_size and current_part:
            # Start new part
            parts.append(current_part)
            current_part = []
            current_size = 2
        
        current_part.append(node)
        current_size += node_size
    
    if current_part:
        parts.append(current_part)
    
    return parts


def add_navigation_links(parts: List[List[Any]], urls: List[str], 
                         title: str) -> List[List[Any]]:
    """Add navigation links between parts."""
    if len(parts) <= 1:
        return parts
    
    result = []
    
    for i, part in enumerate(parts):
        new_part = list(part)
        
        # Add header showing part number
        part_header = {"tag": "p", "children": [
            {"tag": "i", "children": [f"Часть {i + 1} из {len(parts)}"]}
        ]}
        new_part.insert(0, part_header)
        
        # Add navigation at the end
        nav_children: List[Any] = []
        
        if i > 0:
            nav_children.append(
                {"tag": "a", "attrs": {"href": urls[i - 1]}, "children": ["← Назад"]}
            )
            nav_children.append(" | ")
        
        nav_children.append(
            {"tag": "a", "attrs": {"href": urls[0]}, "children": [f"{title} (начало)"]}
        )
        
        if i < len(parts) - 1:
            nav_children.append(" | ")
            nav_children.append(
                {"tag": "a", "attrs": {"href": urls[i + 1]}, "children": ["Далее →"]}
            )
        
        new_part.append({"tag": "hr"})
        new_part.append({"tag": "p", "children": nav_children})
        
        result.append(new_part)
    
    return result


# =============================================================================
# CLI Commands
# =============================================================================


def cmd_create_account(args: argparse.Namespace) -> None:
    """Create Telegraph account."""
    result = create_account(
        short_name=args.short_name,
        author_name=args.author_name,
        author_url=args.author_url
    )
    
    if not result["success"]:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(1)
    
    account = result["result"]
    access_token = account.get("access_token")
    
    if access_token:
        set_telegraph_token(access_token)
        print(json.dumps({
            "success": True,
            "message": "Account created and token saved",
            "account": {
                "short_name": account.get("short_name"),
                "author_name": account.get("author_name"),
                "auth_url": account.get("auth_url")
            }
        }, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"success": False, "error": "No access token in response"}, 
                        ensure_ascii=False, indent=2))
        sys.exit(1)


def cmd_publish(args: argparse.Namespace) -> None:
    """Publish markdown file to Telegraph."""
    # Get token
    token = args.token or get_telegraph_token()
    if not token:
        print(json.dumps({
            "success": False,
            "error": "No Telegraph token. Run 'create-account' first or provide --token"
        }, ensure_ascii=False, indent=2))
        sys.exit(1)
    
    # Read markdown file
    try:
        with open(args.file, "r", encoding="utf-8") as f:
            markdown = f.read()
    except FileNotFoundError:
        print(json.dumps({"success": False, "error": f"File not found: {args.file}"}, 
                        ensure_ascii=False, indent=2))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"success": False, "error": f"Error reading file: {e}"}, 
                        ensure_ascii=False, indent=2))
        sys.exit(1)
    
    # Convert to Telegraph nodes
    content = markdown_to_nodes(markdown)
    
    if not content:
        print(json.dumps({"success": False, "error": "Empty content after conversion"}, 
                        ensure_ascii=False, indent=2))
        sys.exit(1)
    
    # Split if needed
    parts = split_content_for_publishing(content)
    
    if len(parts) == 1:
        # Single page
        result = create_page(
            access_token=token,
            title=args.title,
            content=parts[0],
            author_name=args.author
        )
        
        if not result["success"]:
            print(json.dumps(result, ensure_ascii=False, indent=2))
            sys.exit(1)
        
        page = result["result"]
        print(json.dumps({
            "success": True,
            "url": f"https://telegra.ph/{page['path']}",
            "path": page["path"],
            "title": page["title"],
            "views": page.get("views", 0)
        }, ensure_ascii=False, indent=2))
    else:
        # Multiple pages - create all first, then update with links
        urls = []
        paths = []
        
        # Create placeholder pages
        for i, part in enumerate(parts):
            part_title = f"{args.title} (часть {i + 1})" if i > 0 else args.title
            
            result = create_page(
                access_token=token,
                title=part_title,
                content=part,
                author_name=args.author
            )
            
            if not result["success"]:
                print(json.dumps({
                    "success": False,
                    "error": f"Failed to create part {i + 1}: {result.get('error')}"
                }, ensure_ascii=False, indent=2))
                sys.exit(1)
            
            page = result["result"]
            urls.append(f"https://telegra.ph/{page['path']}")
            paths.append(page["path"])
        
        # Now update all pages with navigation links
        parts_with_nav = add_navigation_links(parts, urls, args.title)
        
        for i, (path, part) in enumerate(zip(paths, parts_with_nav)):
            part_title = f"{args.title} (часть {i + 1})" if i > 0 else args.title
            
            edit_page(
                access_token=token,
                path=path,
                title=part_title,
                content=part,
                author_name=args.author
            )
        
        print(json.dumps({
            "success": True,
            "parts": len(parts),
            "urls": urls,
            "main_url": urls[0]
        }, ensure_ascii=False, indent=2))


def cmd_edit(args: argparse.Namespace) -> None:
    """Edit existing Telegraph page."""
    # Get token
    token = args.token or get_telegraph_token()
    if not token:
        print(json.dumps({
            "success": False,
            "error": "No Telegraph token. Run 'create-account' first or provide --token"
        }, ensure_ascii=False, indent=2))
        sys.exit(1)
    
    # Extract path from URL
    path = args.url
    if path.startswith("https://telegra.ph/"):
        path = path[len("https://telegra.ph/"):]
    elif path.startswith("http://telegra.ph/"):
        path = path[len("http://telegra.ph/"):]
    
    # Get current page to get title
    page_result = get_page(path)
    if not page_result["success"]:
        print(json.dumps({
            "success": False,
            "error": f"Failed to get page: {page_result.get('error')}"
        }, ensure_ascii=False, indent=2))
        sys.exit(1)
    
    current_page = page_result["result"]
    title = args.title or current_page.get("title", "Untitled")
    
    # Read markdown file
    try:
        with open(args.file, "r", encoding="utf-8") as f:
            markdown = f.read()
    except FileNotFoundError:
        print(json.dumps({"success": False, "error": f"File not found: {args.file}"}, 
                        ensure_ascii=False, indent=2))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"success": False, "error": f"Error reading file: {e}"}, 
                        ensure_ascii=False, indent=2))
        sys.exit(1)
    
    # Convert to Telegraph nodes
    content = markdown_to_nodes(markdown)
    
    if not content:
        print(json.dumps({"success": False, "error": "Empty content after conversion"}, 
                        ensure_ascii=False, indent=2))
        sys.exit(1)
    
    # Check size
    if estimate_content_size(content) > MAX_CONTENT_SIZE:
        print(json.dumps({
            "success": False,
            "error": "Content exceeds 64KB limit. Edit doesn't support multi-part. "
                     "Consider publishing as new article."
        }, ensure_ascii=False, indent=2))
        sys.exit(1)
    
    # Edit page
    result = edit_page(
        access_token=token,
        path=path,
        title=title,
        content=content,
        author_name=args.author
    )
    
    if not result["success"]:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(1)
    
    page = result["result"]
    print(json.dumps({
        "success": True,
        "url": f"https://telegra.ph/{page['path']}",
        "path": page["path"],
        "title": page["title"],
        "views": page.get("views", 0)
    }, ensure_ascii=False, indent=2))


def cmd_list(args: argparse.Namespace) -> None:
    """List created pages."""
    # Get token
    token = args.token or get_telegraph_token()
    if not token:
        print(json.dumps({
            "success": False,
            "error": "No Telegraph token. Run 'create-account' first or provide --token"
        }, ensure_ascii=False, indent=2))
        sys.exit(1)
    
    result = get_page_list(
        access_token=token,
        offset=args.offset,
        limit=args.limit
    )
    
    if not result["success"]:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(1)
    
    data = result["result"]
    pages = data.get("pages", [])
    total = data.get("total_count", len(pages))
    
    output = {
        "success": True,
        "total": total,
        "showing": len(pages),
        "offset": args.offset,
        "pages": []
    }
    
    for page in pages:
        output["pages"].append({
            "title": page.get("title"),
            "url": f"https://telegra.ph/{page.get('path')}",
            "path": page.get("path"),
            "views": page.get("views", 0),
            "author_name": page.get("author_name"),
            "description": page.get("description", "")[:100]
        })
    
    print(json.dumps(output, ensure_ascii=False, indent=2))


# =============================================================================
# Main
# =============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Telegraph Publishing CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s create-account --short-name "MyBot" --author-name "AI Assistant"
  %(prog)s publish --file doc.md --title "My Article"
  %(prog)s edit --url "https://telegra.ph/My-Article-01-01" --file updated.md
  %(prog)s list --limit 10

Configuration:
  Access token stored in: ~/.openclaw/ton-skill/config.json
"""
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # create-account
    create_parser = subparsers.add_parser(
        "create-account",
        help="Create Telegraph account"
    )
    create_parser.add_argument(
        "--short-name", "-s",
        required=True,
        help="Short name for the account (1-32 chars)"
    )
    create_parser.add_argument(
        "--author-name", "-a",
        help="Default author name for pages (0-128 chars)"
    )
    create_parser.add_argument(
        "--author-url",
        help="Default author profile URL"
    )
    
    # publish
    publish_parser = subparsers.add_parser(
        "publish",
        help="Publish markdown file to Telegraph"
    )
    publish_parser.add_argument(
        "--file", "-f",
        required=True,
        help="Path to markdown file"
    )
    publish_parser.add_argument(
        "--title", "-t",
        required=True,
        help="Page title (1-256 chars)"
    )
    publish_parser.add_argument(
        "--author", "-a",
        help="Author name for this page"
    )
    publish_parser.add_argument(
        "--token",
        help="Access token (default: from config)"
    )
    
    # edit
    edit_parser = subparsers.add_parser(
        "edit",
        help="Edit existing Telegraph page"
    )
    edit_parser.add_argument(
        "--url", "-u",
        required=True,
        help="Telegraph page URL or path"
    )
    edit_parser.add_argument(
        "--file", "-f",
        required=True,
        help="Path to markdown file"
    )
    edit_parser.add_argument(
        "--title", "-t",
        help="New title (default: keep current)"
    )
    edit_parser.add_argument(
        "--author", "-a",
        help="Author name"
    )
    edit_parser.add_argument(
        "--token",
        help="Access token (default: from config)"
    )
    
    # list
    list_parser = subparsers.add_parser(
        "list",
        help="List created pages"
    )
    list_parser.add_argument(
        "--limit", "-l",
        type=int,
        default=10,
        help="Number of pages to return (default: 10, max: 200)"
    )
    list_parser.add_argument(
        "--offset", "-o",
        type=int,
        default=0,
        help="Offset for pagination"
    )
    list_parser.add_argument(
        "--token",
        help="Access token (default: from config)"
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    commands = {
        "create-account": cmd_create_account,
        "publish": cmd_publish,
        "edit": cmd_edit,
        "list": cmd_list,
    }
    
    cmd_func = commands.get(args.command)
    if cmd_func:
        cmd_func(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
