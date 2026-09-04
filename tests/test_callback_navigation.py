from __future__ import annotations

import ast
from pathlib import Path

BOT_SOURCE = Path(__file__).parents[1] / "src/skyblock_monitor/bot.py"


def _callback_handlers(tree: ast.Module) -> list[ast.AsyncFunctionDef]:
    handlers = []
    for node in tree.body:
        if not isinstance(node, ast.AsyncFunctionDef):
            continue
        if any(
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and decorator.func.attr == "callback_query"
            for decorator in node.decorator_list
        ):
            handlers.append(node)
    return handlers


def test_callback_buttons_never_send_a_new_message():
    tree = ast.parse(BOT_SOURCE.read_text())
    violations = []
    for handler in _callback_handlers(tree):
        for node in ast.walk(handler):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            owner = node.func.value
            if (
                node.func.attr in {"answer", "answer_photo"}
                and isinstance(owner, ast.Attribute)
                and isinstance(owner.value, ast.Name)
                and owner.value.id == "query"
                and owner.attr == "message"
            ):
                violations.append(handler.name)
    assert violations == []


def test_start_creates_media_screen_that_callbacks_can_edit():
    tree = ast.parse(BOT_SOURCE.read_text())
    start = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "start")
    method_names = {
        node.func.attr
        for node in ast.walk(start)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "answer_photo" in method_names
