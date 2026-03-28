import uuid as _uuid
from collections import defaultdict

from langchain_core.tools import tool
from sqlalchemy import select
from sqlalchemy.orm import defer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependancies import EmbeddingConfig
from app.models.book import Book
from app.models.manuscript_node import ManuscriptNode
from app.services.rag import query_book


def make_book_tools(book: Book, db: AsyncSession, embedding_config: EmbeddingConfig) -> list:
    """Return the list of LangChain tools scoped to a specific book."""

    @tool
    def search_book(query: str) -> str:
        """Search the book content semantically. Use this to find specific mentions of a topic, character, or event.
        IMPORTANT: The results are short excerpts. If you find a relevant excerpt and need to understand the whole scene, 
        note the 'node_title' or 'id' from these results, and then use the `read_chapter` tool to read the full text."""
        results = query_book(book, query, embedding_config, k=7)
        parts = []
        for r in results["results"]:
            parts.append(f"[{r['metadata']['node_title']}]\n{r['content']}")
        return "\n---\n".join(parts) if parts else "No results found."

    @tool
    async def read_chapter(identifier: str) -> str:
        """Read the full, detailed text of a specific chapter or scene.
        Pass the exact ID (UUID) or the title of the chapter.
        If you don't know the exact ID or title, you MUST use the `list_chapters` tool first to find it.
        After reading, you can answer the user or use `search_book` if you need to cross-reference something else."""
        node = None
        # Try UUID first
        try:
            fid = _uuid.UUID(identifier)
            result = await db.execute(
                select(ManuscriptNode).where(
                    ManuscriptNode.book_id == book.id,
                    ManuscriptNode.front_id == fid,
                )
            )
            node = result.scalar_one_or_none()
        except ValueError:
            pass
        # Fuzzy title fallback
        if not node:
            result = await db.execute(
                select(ManuscriptNode).where(
                    ManuscriptNode.book_id == book.id,
                    ManuscriptNode.title.ilike(f"%{identifier}%"),
                )
            )
            node = result.scalar_one_or_none()
        if not node:
            return f"No chapter found matching '{identifier}'."

        # Load all nodes for this book to build the subtree
        all_result = await db.execute(
            select(ManuscriptNode)
            .where(ManuscriptNode.book_id == book.id)
            .order_by(ManuscriptNode.position)
        )
        all_nodes = all_result.scalars().all()

        children_map: dict = defaultdict(list)
        for n in all_nodes:
            if n.parent_front_id is not None:
                children_map[n.parent_front_id].append(n)

        parts = []

        def render_node(n: ManuscriptNode, depth: int) -> None:
            heading = "#" * min(depth + 1, 6)
            parts.append(f"{heading} {n.title} (id: {n.front_id})")
            if n.content:
                parts.append(n.content)
            for child in children_map.get(n.front_id, []):
                render_node(child, depth + 1)

        has_children = bool(children_map.get(node.front_id))
        if not has_children:
            # Leaf node: simple output without redundant header overhead
            if not node.content:
                return f"'{node.title}' has no text content."
            return f"# {node.title} (id: {node.front_id})\n\n{node.content}"

        render_node(node, 1)
        return "\n\n".join(parts)

    @tool
    async def list_chapters() -> str:
        """Returns the complete table of contents of the manuscript (chapters, scenes, parts) with their precise IDs.
        ALWAYS use this tool first if you need to understand the chronology of the book or if you need to find a specific chapter ID to pass to the `read_chapter` tool."""
        result = await db.execute(
            select(ManuscriptNode)
            .where(ManuscriptNode.book_id == book.id)
            .options(defer(ManuscriptNode.content))
            .order_by(ManuscriptNode.position)
        )
        nodes = result.scalars().all()
        if not nodes:
            return "No chapters found."

        # Build tree: parent_front_id -> [children sorted by position]
        children_map: dict = defaultdict(list)
        roots = []
        for node in nodes:
            if node.parent_front_id is None:
                roots.append(node)
            else:
                children_map[node.parent_front_id].append(node)

        lines = []

        def render(node, depth: int) -> None:
            indent = "  " * depth
            lines.append(f"[{node.node_type}] {indent}{node.title} (id: {node.front_id})")
            for child in children_map.get(node.front_id, []):
                render(child, depth + 1)

        for root in roots:
            render(root, 0)

        return "\n".join(lines)

    return [search_book, read_chapter, list_chapters]
