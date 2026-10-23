"""Community chess for the profile README, driven by GitHub issues.

Issue title format: `chess|move|e2e4` or `chess|new` (only allowed once a game is over).
Reads ISSUE_TITLE / ISSUE_AUTHOR from env, writes the reply to chess/reply.md and
`status=ok|invalid` to $GITHUB_OUTPUT. Never shells out: the issue title is untrusted input.

Local bootstrap (renders the README section for a fresh game): python3 scripts/chess_move.py --init
"""

import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import quote

import chess
import chess.svg

REPO = 'baotpt-crypto/baotpt-crypto'
ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = ROOT / 'chess' / 'state.json'
BOARD_PATH = ROOT / 'chess' / 'board.svg'
REPLY_PATH = ROOT / 'chess' / 'reply.md'
README_PATH = ROOT / 'README.md'
SECTION_PATTERN = re.compile(r'<!-- CHESS:START -->.*<!-- CHESS:END -->', re.S)
RECENT_MOVES_SHOWN = 5

BOARD_COLORS = {
    'square light': '#ffd6e7',
    'square dark': '#d6336c',
    'square light lastmove': '#ffe066',
    'square dark lastmove': '#f59f00',
    'margin': '#1a1b27',
    'coord': '#ffd6e7',
}
PIECE_ICONS = {
    chess.PAWN: '♟',
    chess.KNIGHT: '♞',
    chess.BISHOP: '♝',
    chess.ROOK: '♜',
    chess.QUEEN: '♛',
    chess.KING: '♚',
}


def new_state(game_number: int) -> dict:
    return {'game': game_number, 'fen': chess.STARTING_FEN, 'moves': []}


def load_state() -> dict:
    if not STATE_PATH.exists():
        return new_state(1)
    return json.loads(STATE_PATH.read_text(encoding='utf-8'))


def issue_link(title: str, label: str) -> str:
    body = quote('Just press **Submit new issue**, a bot will play your move ♟️')
    return f'[{label}](https://github.com/{REPO}/issues/new?title={quote(title)}&body={body})'


def outcome_text(board: chess.Board) -> str:
    outcome = board.outcome()
    if outcome is None:
        return ''
    if outcome.winner is None:
        return f'🤝 Draw ({outcome.termination.name.replace("_", " ").lower()})'
    winner = 'White' if outcome.winner == chess.WHITE else 'Black'
    return f'🏆 {winner} wins by {outcome.termination.name.replace("_", " ").lower()}'


def render_legal_moves(board: chess.Board) -> str:
    moves_by_square: dict[int, list[chess.Move]] = {}
    for move in board.legal_moves:
        moves_by_square.setdefault(move.from_square, []).append(move)

    rows = []
    for from_square in sorted(moves_by_square):
        piece = board.piece_at(from_square)
        links = ' '.join(
            issue_link(f'chess|move|{move.uci()}', chess.square_name(move.to_square) + (move.uci()[4:] or ''))
            for move in sorted(moves_by_square[from_square], key=lambda m: m.uci())
        )
        rows.append(f'| {PIECE_ICONS[piece.piece_type]} **{chess.square_name(from_square)}** | {links} |')
    return '| Piece | Move to |\n|:-:|:--|\n' + '\n'.join(rows)


def render_section(state: dict, board: chess.Board) -> str:
    move_count = len(state['moves'])
    board_url = f'https://raw.githubusercontent.com/{REPO}/main/chess/board.svg?v={state["game"]}-{move_count}'
    lines = [
        '<!-- CHESS:START -->',
        '<p align="center">',
        f'  <picture><img src="{board_url}" width="360" alt="Chess board" /></picture>',
        '</p>',
        '',
    ]

    result = outcome_text(board)
    if result:
        lines += [f'**Game #{state["game"]} is over: {result}!** {issue_link("chess|new", "👉 Start a new game")}', '']
    else:
        side = '⚪ White' if board.turn == chess.WHITE else '⚫ Black'
        check = ' — **check!**' if board.is_check() else ''
        lines += [
            f'**Game #{state["game"]}** · move {board.fullmove_number} · it\'s **{side}**\'s turn{check}. '
            'Anyone can play: click a move below and submit the issue.',
            '',
            '<details><summary><b>🎯 Pick your move</b></summary>',
            '',
            render_legal_moves(board),
            '',
            '</details>',
            '',
        ]

    recent = state['moves'][-RECENT_MOVES_SHOWN:]
    if recent:
        lines += ['| Recent move | Played by |', '|:-:|:--|']
        lines += [f'| `{move["san"]}` | [@{move["player"]}](https://github.com/{move["player"]}) |' for move in reversed(recent)]
        lines.append('')

    lines.append('<!-- CHESS:END -->')
    return '\n'.join(lines)


def write_outputs(state: dict, board: chess.Board) -> None:
    last_move = board.peek() if board.move_stack else None
    BOARD_PATH.parent.mkdir(exist_ok=True)
    BOARD_PATH.write_text(
        chess.svg.board(board, size=360, lastmove=last_move, colors=BOARD_COLORS, check=board.king(board.turn) if board.is_check() else None),
        encoding='utf-8',
    )
    STATE_PATH.write_text(json.dumps(state, indent=2) + '\n', encoding='utf-8')
    readme = README_PATH.read_text(encoding='utf-8')
    README_PATH.write_text(SECTION_PATTERN.sub(lambda _: render_section(state, board), readme), encoding='utf-8')


def board_from_state(state: dict) -> chess.Board:
    board = chess.Board()
    for move in state['moves']:
        board.push_uci(move['uci'])
    return board


def handle_issue(title: str, author: str) -> tuple[str, str]:
    """Apply the issue's command. Returns (status, reply markdown)."""
    state = load_state()
    board = board_from_state(state)
    parts = title.strip().split('|')

    if parts == ['chess', 'new']:
        if not board.is_game_over():
            return 'invalid', 'A game is still in progress, finish it first 😉'
        state = new_state(state['game'] + 1)
        write_outputs(state, chess.Board())
        return 'ok', f'🎉 @{author} started game #{state["game"]}. White to move!'

    if len(parts) != 3 or parts[:2] != ['chess', 'move']:
        return 'invalid', 'Unknown command. Use the move links in the README ♟️'
    if board.is_game_over():
        return 'invalid', 'This game is over, start a new one from the README.'

    try:
        move = chess.Move.from_uci(parts[2].lower())
    except ValueError:
        return 'invalid', 'That is not a valid move format. Use the move links in the README ♟️'
    if move not in board.legal_moves:
        return 'invalid', f'`{move.uci()}` is not legal in the current position. Someone may have moved first, check the README again!'

    san = board.san(move)
    board.push(move)
    state['moves'].append({'uci': move.uci(), 'san': san, 'player': author})
    state['fen'] = board.fen()
    write_outputs(state, board)

    reply = f'✅ @{author} played **{san}**. Thanks for playing!'
    result = outcome_text(board)
    if result:
        reply += f'\n\n{result}!'
    return 'ok', reply


def main() -> None:
    if '--init' in sys.argv:
        state = load_state()
        write_outputs(state, board_from_state(state))
        print('Rendered chess section')
        return

    # GitHub usernames are [A-Za-z0-9-]; anything else is dropped before it lands in markdown
    author = re.sub(r'[^A-Za-z0-9-]', '', os.environ.get('ISSUE_AUTHOR', ''))
    status, reply = handle_issue(os.environ.get('ISSUE_TITLE', ''), author)
    REPLY_PATH.write_text(reply + '\n', encoding='utf-8')
    with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
        output.write(f'status={status}\n')
    print(status, reply)


if __name__ == '__main__':
    main()
