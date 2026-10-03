#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
weiqi-db 围棋棋谱数据库
本地棋谱管理工具，AI友好的JSON接口设计

依赖: pip3 install tinydb
"""

import os
import sys
import re
import json
import hashlib
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

# TinyDB
from tinydb import TinyDB, Query
from tinydb.operations import add, delete

# 数据库路径
DB_DIR = Path.home() / ".weiqi-db"
DB_PATH = DB_DIR / "database.json"

# SGF 解析正则
SGF_PATTERNS = {
    'PB': r'PB\[([^\]]*)\]',
    'PW': r'PW\[([^\]]*)\]',
    'BR': r'BR\[([^\]]*)\]',
    'WR': r'WR\[([^\]]*)\]',
    'DT': r'DT\[([^\]]*)\]',
    'EV': r'EV\[([^\]]*)\]',
    'GN': r'GN\[([^\]]*)\]',
    'RE': r'RE\[([^\]]*)\]',
    'KM': r'KM\[([^\]]*)\]',
    'HA': r'HA\[(\d+)\]',
}


def ensure_db() -> TinyDB:
    """确保数据库存在并返回实例"""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    return TinyDB(DB_PATH)


def parse_sgf(sgf_content: str) -> Dict[str, Any]:
    """从SGF内容解析元数据"""
    info = {}
    
    for key, pattern in SGF_PATTERNS.items():
        match = re.search(pattern, sgf_content)
        if match:
            info[key] = match.group(1)
    
    # 计算手数
    moves = re.findall(r';[BW]\[[a-z]{2}\]', sgf_content)
    info['movenum'] = len(moves)
    
    # 标准化字段名
    result = {
        'black': info.get('PB', '黑棋'),
        'white': info.get('PW', '白棋'),
        'black_rank': info.get('BR', ''),
        'white_rank': info.get('WR', ''),
        'date': info.get('DT', ''),
        'event': info.get('EV', info.get('GN', '')),
        'result': info.get('RE', ''),
        'komi': info.get('KM', ''),
        'handicap': int(info.get('HA', 0)),
        'movenum': info.get('movenum', 0),
    }
    
    return result


def calc_hash(sgf_content: str) -> str:
    """计算SGF内容哈希（去重用）"""
    # 移除空白字符后计算哈希
    normalized = re.sub(r'\s+', '', sgf_content.strip())
    return hashlib.md5(normalized.encode('utf-8')).hexdigest()[:16]


def calc_similarity_hash(sgf_content: str) -> str:
    """计算棋谱相似度哈希（用于检测同一盘棋的不同SGF版本）
    
    忽略以下可变字段：
    - 文件头信息（FF, AP, SZ等）
    - 时间戳、日期格式差异
    - 注释和标记
    只保留：棋盘大小、 handicap、对局实质内容（落子序列）
    """
    # 移除所有空白
    normalized = re.sub(r'\s+', '', sgf_content.strip())
    
    # 提取关键信息
    size_match = re.search(r'SZ\[(\d+)\]', normalized)
    size = size_match.group(1) if size_match else '19'
    
    # 提取 handicap
    handicap_match = re.search(r'HA\[(\d+)\]', normalized)
    handicap = handicap_match.group(1) if handicap_match else '0'
    
    # 提取所有落子（只保留坐标，去掉注释、标记等）
    moves = re.findall(r';[BW]\[([a-z]{2})\]', normalized)
    move_seq = ''.join(moves)
    
    # 组合关键信息计算哈希
    key_content = f"SZ:{size}|HA:{handicap}|MOVES:{move_seq}"
    return hashlib.md5(key_content.encode('utf-8')).hexdigest()[:16]


def find_conflicts(table, meta: Dict[str, Any], content_hash: str, similarity_hash: str) -> List[Dict[str, Any]]:
    """查找可能的冲突记录
    
    冲突类型：
    1. exact - 完全重复（内容哈希相同）
    2. similar - 相似棋谱（日期+黑白棋手相同）
    3. potential - 潜在重复（相似哈希相同但内容不同）
    """
    conflicts = []
    
    for game in table.all():
        conflict_type = None
        
        # 检查完全重复
        if game.get('hash') == content_hash:
            conflict_type = 'exact'
        # 检查相似哈希（同一盘棋的不同SGF版本）
        elif game.get('similarity_hash') == similarity_hash:
            conflict_type = 'potential'
        # 检查日期+棋手组合（同一盘棋的标识）
        elif (meta.get('date') and meta.get('date') == game.get('date') and
              meta.get('black') and meta.get('white') and
              meta.get('black') == game.get('black') and
              meta.get('white') == game.get('white')):
            conflict_type = 'similar'
        
        if conflict_type:
            conflicts.append({
                'id': game.get('id'),
                'type': conflict_type,
                'existing': {k: v for k, v in game.items() if k not in ('sgf', 'hash', 'similarity_hash')},
                'diff': calc_diff(meta, game)
            })
    
    return conflicts


def calc_diff(new_meta: Dict[str, Any], existing: Dict[str, Any]) -> Dict[str, Any]:
    """计算新旧记录的元数据差异"""
    diff = {}
    fields = ['black', 'white', 'black_rank', 'white_rank', 'date', 'event', 'result', 'komi', 'movenum']
    
    for field in fields:
        old_val = existing.get(field, '')
        new_val = new_meta.get(field, '')
        if old_val != new_val:
            diff[field] = {'old': old_val, 'new': new_val}
    
    return diff


_id_counter = 0

def generate_id() -> str:
    """生成唯一ID（时间戳+递增序号）"""
    global _id_counter
    _id_counter += 1
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    return f"{timestamp}{_id_counter:04d}"


def format_output(data: Any) -> str:
    """格式化JSON输出"""
    return json.dumps(data, ensure_ascii=False, indent=2)


def cmd_init(args):
    """初始化数据库"""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    db = TinyDB(DB_PATH)
    
    # 初始化空表
    if 'games' not in db.tables():
        db.table('games')
    
    return {
        "success": True,
        "path": str(DB_PATH),
        "message": "数据库初始化成功"
    }


def find_conflicts(table, meta: Dict[str, Any], content_hash: str) -> List[Dict]:
    """
    查找可能的冲突棋谱
    冲突类型：
    1. 哈希完全重复（相同SGF内容）
    2. 元数据重复（同棋手、同日期、可能同一局棋）
    """
    conflicts = []
    all_games = table.all()
    
    for game in all_games:
        conflict_type = None
        
        # 类型1: 哈希完全重复
        if game.get('hash') == content_hash:
            conflict_type = 'hash'
        # 类型2: 元数据重复（同棋手 + 同日期）
        elif (game.get('black') == meta.get('black') and 
              game.get('white') == meta.get('white') and
              game.get('date') == meta.get('date') and
              meta.get('date')):  # 确保日期不为空
            # 进一步检查：手数相近或结果相同
            if (game.get('movenum') == meta.get('movenum') or
                game.get('result') == meta.get('result')):
                conflict_type = 'metadata'
        
        if conflict_type:
            conflicts.append({
                'id': game.get('id'),
                'type': conflict_type,
                'game': game
            })
    
    return conflicts


def cmd_add(args):
    """添加棋谱"""
    db = ensure_db()
    table = db.table('games')
    
    results = []
    added_count = 0
    skipped_count = 0
    overwritten_count = 0
    conflict_details = []
    
    # 冲突处理策略
    conflict_strategy = getattr(args, 'conflict', 'skip')  # skip, overwrite, keep
    
    # 收集要添加的文件
    files = []
    if args.file:
        files.append(Path(args.file))
    elif args.dir:
        dir_path = Path(args.dir)
        if dir_path.exists():
            files.extend(sorted(dir_path.glob('*.sgf')))
    
    if not files:
        return {"success": False, "error": "未找到SGF文件"}
    
    # 获取已有哈希（去重用）
    existing_hashes = {g.get('hash', '') for g in table.all()}
    
    for file_path in files:
        if not file_path.exists():
            results.append({"file": str(file_path), "success": False, "error": "文件不存在"})
            continue
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                sgf_content = f.read()
            
            # 计算哈希
            content_hash = calc_hash(sgf_content)
            
            # 解析SGF
            meta = parse_sgf(sgf_content)
            
            # 检查冲突
            conflicts = find_conflicts(table, meta, content_hash)
            
            if conflicts:
                conflict = conflicts[0]  # 取第一个冲突
                conflict_type = conflict['type']
                existing_id = conflict['id']
                
                if conflict_strategy == 'skip':
                    skipped_count += 1
                    conflict_details.append({
                        "file": str(file_path),
                        "action": "skipped",
                        "conflict_type": conflict_type,
                        "existing_id": existing_id
                    })
                    conflict_desc = '相同棋谱' if conflict_type == 'hash' else '可能重复'
                    results.append({
                        "file": str(file_path), 
                        "success": False, 
                        "error": f"冲突: {conflict_desc}",
                        "conflict_type": conflict_type,
                        "existing_id": existing_id
                    })
                    continue
                
                elif conflict_strategy == 'overwrite':
                    # 删除旧记录，添加新记录
                    Game = Query()
                    table.remove(Game.id == existing_id)
                    existing_hashes.discard(conflict['game'].get('hash', ''))
                    overwritten_count += 1
                    conflict_details.append({
                        "file": str(file_path),
                        "action": "overwritten",
                        "conflict_type": conflict_type,
                        "existing_id": existing_id
                    })
                
                elif conflict_strategy == 'keep':
                    # 保留两者，不做任何处理，直接添加
                    pass
            
            # 命令行参数覆盖
            if args.black:
                meta['black'] = args.black
            if args.white:
                meta['white'] = args.white
            if args.black_rank:
                meta['black_rank'] = args.black_rank
            if args.white_rank:
                meta['white_rank'] = args.white_rank
            if args.date:
                meta['date'] = args.date
            if args.event:
                meta['event'] = args.event
            if args.result:
                meta['result'] = args.result
            if args.komi:
                meta['komi'] = args.komi
            
            # 构建记录
            game_id = generate_id()
            record = {
                "id": game_id,
                "sgf": sgf_content,
                "hash": content_hash,
                "black": meta['black'],
                "white": meta['white'],
                "black_rank": meta['black_rank'],
                "white_rank": meta['white_rank'],
                "date": meta['date'],
                "event": meta['event'],
                "result": meta['result'],
                "komi": meta['komi'],
                "handicap": meta.get('handicap', 0),
                "movenum": meta['movenum'],
                "tags": args.tag if args.tag else [],
                "created": datetime.now().isoformat()
            }
            
            table.insert(record)
            existing_hashes.add(content_hash)
            added_count += 1
            
            results.append({
                "file": str(file_path),
                "success": True,
                "id": game_id,
                "fields": {
                    "black": record['black'],
                    "white": record['white'],
                    "date": record['date'],
                    "event": record['event']
                }
            })
            
        except Exception as e:
            results.append({"file": str(file_path), "success": False, "error": str(e)})
    
    return {
        "success": True,
        "added": added_count,
        "skipped": skipped_count,
        "overwritten": overwritten_count,
        "total": len(files),
        "conflict_strategy": conflict_strategy,
        "conflicts": conflict_details,
        "results": results
    }


def match_condition(game: Dict, key: str, value: Any) -> bool:
    """单条件匹配"""
    # 特殊字段 player: 匹配 black 或 white
    if key == 'player':
        return value.lower() in game.get('black', '').lower() or \
               value.lower() in game.get('white', '').lower()
    
    # 模糊匹配 (~后缀)
    if key.endswith('~'):
        field = key[:-1]
        return value.lower() in str(game.get(field, '')).lower()
    
    # 大于等于 (>=后缀)
    if key.endswith('>='):
        field = key[:-2]
        return str(game.get(field, '')) >= str(value)
    
    # 小于等于 (<=后缀)
    if key.endswith('<='):
        field = key[:-2]
        return str(game.get(field, '')) <= str(value)
    
    # 大于 (>后缀)
    if key.endswith('>'):
        field = key[:-1]
        return str(game.get(field, '')) > str(value)
    
    # 小于 (<后缀)
    if key.endswith('<'):
        field = key[:-1]
        return str(game.get(field, '')) < str(value)
    
    # 标签特殊处理
    if key == 'tags':
        tags = game.get('tags', [])
        return value in tags
    
    # keyword: 全字段模糊搜索
    if key == 'keyword':
        keyword = value.lower()
        fields_to_search = ['black', 'white', 'event', 'result', 'date', 'sgf']
        for field in fields_to_search:
            if keyword in str(game.get(field, '')).lower():
                return True
        return False
    
    # 默认精确匹配
    return game.get(key) == value


def evaluate_where(game: Dict, where: Dict) -> bool:
    """递归评估 where 条件"""
    if not where:
        return True
    
    # $and: 所有条件都满足
    if '$and' in where:
        return all(evaluate_where(game, cond) for cond in where['$and'])
    
    # $or: 任一条件满足
    if '$or' in where:
        return any(evaluate_where(game, cond) for cond in where['$or'])
    
    # $not: 条件不满足
    if '$not' in where:
        return not evaluate_where(game, where['$not'])
    
    # 普通字段匹配
    for key, value in where.items():
        if not match_condition(game, key, value):
            return False
    
    return True


def cmd_query(args):
    """查询棋谱"""
    db = ensure_db()
    table = db.table('games')
    
    # 解析 where 条件
    where = {}
    if args.where:
        try:
            where = json.loads(args.where)
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"JSON解析错误: {e}"}
    
    # 过滤
    games = [g for g in table.all() if evaluate_where(g, where)]
    
    # 排序
    if args.sort:
        reverse = args.sort.startswith('-')
        sort_key = args.sort.lstrip('-')
        games.sort(key=lambda x: x.get(sort_key, ''), reverse=reverse)
    else:
        # 默认按日期倒序
        games.sort(key=lambda x: x.get('date', ''), reverse=True)
    
    # 限制数量
    total = len(games)
    if args.limit:
        games = games[:args.limit]
    
    # 清理输出（移除SGF内容，减少体积）
    clean_games = []
    for g in games:
        cg = {k: v for k, v in g.items() if k != 'sgf' and k != 'hash'}
        clean_games.append(cg)
    
    return {
        "success": True,
        "count": len(clean_games),
        "total": total,
        "games": clean_games
    }


def cmd_list(args):
    """列出所有棋谱"""
    db = ensure_db()
    table = db.table('games')
    
    games = table.all()
    
    # 排序
    games.sort(key=lambda x: x.get('date', ''), reverse=True)
    
    total = len(games)
    if args.limit:
        games = games[:args.limit]
    
    # 清理输出
    clean_games = []
    for g in games:
        cg = {k: v for k, v in g.items() if k != 'sgf' and k != 'hash'}
        clean_games.append(cg)
    
    return {
        "success": True,
        "count": len(clean_games),
        "total": total,
        "games": clean_games
    }


def cmd_update(args):
    """更新元数据"""
    db = ensure_db()
    table = db.table('games')
    
    if not args.id:
        return {"success": False, "error": "需要指定 --id"}
    
    try:
        updates = json.loads(args.set) if args.set else {}
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"JSON解析错误: {e}"}
    
    Game = Query()
    games = table.search(Game.id == args.id)
    
    if not games:
        return {"success": False, "error": f"未找到ID: {args.id}"}
    
    # 更新字段
    table.update(updates, Game.id == args.id)
    
    return {
        "success": True,
        "id": args.id,
        "updated": list(updates.keys())
    }


def cmd_tag(args):
    """标签管理"""
    db = ensure_db()
    table = db.table('games')
    
    if not args.id:
        return {"success": False, "error": "需要指定 --id"}
    
    Game = Query()
    games = table.search(Game.id == args.id)
    
    if not games:
        return {"success": False, "error": f"未找到ID: {args.id}"}
    
    if args.add:
        # 添加标签（避免重复）
        def add_tag(doc):
            tags = doc.get('tags', [])
            if args.add not in tags:
                tags.append(args.add)
            return {'tags': tags}
        
        table.update(add_tag, Game.id == args.id)
        return {"success": True, "id": args.id, "action": "add_tag", "tag": args.add}
    
    elif args.remove:
        # 移除标签
        def remove_tag(doc):
            tags = doc.get('tags', [])
            if args.remove in tags:
                tags.remove(args.remove)
            return {'tags': tags}
        
        table.update(remove_tag, Game.id == args.id)
        return {"success": True, "id": args.id, "action": "remove_tag", "tag": args.remove}
    
    else:
        # 显示当前标签
        game = games[0]
        return {"success": True, "id": args.id, "tags": game.get('tags', [])}


def cmd_delete(args):
    """删除棋谱"""
    db = ensure_db()
    table = db.table('games')
    
    if not args.id:
        return {"success": False, "error": "需要指定 --id"}
    
    Game = Query()
    games = table.search(Game.id == args.id)
    
    if not games:
        return {"success": False, "error": f"未找到ID: {args.id}"}
    
    table.remove(Game.id == args.id)
    
    return {
        "success": True,
        "id": args.id,
        "deleted": True
    }


def cmd_clear(args):
    """清空数据库 - 直接重写文件确保彻底清空"""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    
    # 直接重写 JSON 文件，绕过 TinyDB 的缓存机制
    empty_db = {"games": {}}
    with open(DB_PATH, 'w', encoding='utf-8') as f:
        json.dump(empty_db, f, ensure_ascii=False, indent=2)
    
    # 验证清空结果
    db = TinyDB(DB_PATH)
    table = db.table('games')
    count = len(table.all())
    
    return {
        "success": True,
        "message": "数据库已清空",
        "remaining_records": count
    }


def cmd_stats(args):
    """统计信息"""
    db = ensure_db()
    table = db.table('games')
    
    games = table.all()
    total = len(games)
    
    # 棋手统计
    players = {}
    for g in games:
        for color, field in [('black', 'black'), ('white', 'white')]:
            name = g.get(field, '未知')
            if name not in players:
                players[name] = {'total': 0, 'as_black': 0, 'as_white': 0}
            players[name]['total'] += 1
            if color == 'black':
                players[name]['as_black'] += 1
            else:
                players[name]['as_white'] += 1
    
    # 标签统计
    tags = {}
    for g in games:
        for tag in g.get('tags', []):
            tags[tag] = tags.get(tag, 0) + 1
    
    # 赛事统计
    events = {}
    for g in games:
        event = g.get('event', '未知')
        if event:
            events[event] = events.get(event, 0) + 1
    
    # 日期范围
    dates = [g.get('date', '') for g in games if g.get('date')]
    date_range = {
        'earliest': min(dates) if dates else None,
        'latest': max(dates) if dates else None
    }
    
    return {
        "success": True,
        "total_games": total,
        "date_range": date_range,
        "top_players": sorted(players.items(), key=lambda x: x[1]['total'], reverse=True)[:10],
        "top_tags": sorted(tags.items(), key=lambda x: x[1], reverse=True)[:10],
        "top_events": sorted(events.items(), key=lambda x: x[1], reverse=True)[:10]
    }


def main():
    parser = argparse.ArgumentParser(description='围棋棋谱数据库')
    parser.add_argument('--json', action='store_true', help='JSON格式输出')
    subparsers = parser.add_subparsers(dest='command', help='命令')
    
    # init
    subparsers.add_parser('init', help='初始化数据库')
    
    # clear
    subparsers.add_parser('clear', help='清空所有棋谱')
    
    # add
    add_parser = subparsers.add_parser('add', help='添加棋谱')
    add_parser.add_argument('--file', help='单个SGF文件')
    add_parser.add_argument('--dir', help='SGF目录')
    add_parser.add_argument('--black', help='黑棋名')
    add_parser.add_argument('--white', help='白棋名')
    add_parser.add_argument('--black-rank', help='黑棋段位')
    add_parser.add_argument('--white-rank', help='白棋段位')
    add_parser.add_argument('--date', help='对局日期')
    add_parser.add_argument('--event', help='赛事名称')
    add_parser.add_argument('--result', help='对局结果')
    add_parser.add_argument('--komi', help='贴目')
    add_parser.add_argument('--tag', action='append', help='标签（可多次指定）')
    add_parser.add_argument('--conflict', choices=['skip', 'overwrite', 'keep'], 
                           default='skip', help='冲突处理策略: skip(跳过), overwrite(覆盖), keep(保留两者)')
    
    # query
    query_parser = subparsers.add_parser('query', help='查询棋谱')
    query_parser.add_argument('--where', help='查询条件（JSON）')
    query_parser.add_argument('--sort', help='排序字段（前缀-表示倒序）')
    query_parser.add_argument('--limit', type=int, help='限制数量')
    
    # list
    list_parser = subparsers.add_parser('list', help='列出所有棋谱')
    list_parser.add_argument('--limit', type=int, help='限制数量')
    
    # update
    update_parser = subparsers.add_parser('update', help='更新元数据')
    update_parser.add_argument('--id', required=True, help='棋谱ID')
    update_parser.add_argument('--set', required=True, help='更新内容（JSON）')
    
    # tag
    tag_parser = subparsers.add_parser('tag', help='标签管理')
    tag_parser.add_argument('--id', required=True, help='棋谱ID')
    tag_parser.add_argument('--add', help='添加标签')
    tag_parser.add_argument('--remove', help='移除标签')
    
    # delete
    delete_parser = subparsers.add_parser('delete', help='删除棋谱')
    delete_parser.add_argument('--id', required=True, help='棋谱ID')
    
    # stats
    subparsers.add_parser('stats', help='统计信息')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # 执行命令
    commands = {
        'init': cmd_init,
        'clear': cmd_clear,
        'add': cmd_add,
        'query': cmd_query,
        'list': cmd_list,
        'update': cmd_update,
        'tag': cmd_tag,
        'delete': cmd_delete,
        'stats': cmd_stats,
    }
    
    result = commands[args.command](args)
    
    # 输出结果
    if args.json or True:  # 默认JSON输出
        print(format_output(result))
    
    # 根据结果返回退出码
    sys.exit(0 if result.get('success', True) else 1)


if __name__ == '__main__':
    main()
