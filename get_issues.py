import requests
import json
import argparse
import os
from datetime import datetime

# --- 配置信息（从环境变量读取） ---
JIRA_URL = os.getenv("JIRA_URL", "https://issues.redhat.com")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "Konflux UI")

# 使用 Bearer Token 认证（匹配 test_auth.py 的工作方式）
headers = {
    "Accept": "application/json",
    "authorization": f"Bearer {JIRA_API_TOKEN}"
}

def fetch_jira_data(jql_query, start_at=0, max_results=50, expand=None):
    """
    通用函数，用于分页拉取Jira Issue数据。
    """
    url = f"{JIRA_URL}/rest/api/2/search"

    # 构建查询参数
    params = {
        'jql': jql_query,
        'fields': 'created,resolutiondate,status,issuetype,timeoriginalestimate,timetracking', # 需要获取的字段
        'startAt': start_at,
        'maxResults': max_results
    }

    if expand:
        params['expand'] = expand

    # DEBUG: 打印完整的请求信息
    print(f"\n[DEBUG] === Jira API Request ===")
    print(f"[DEBUG] URL: {url}")
    print(f"[DEBUG] JQL Query: {jql_query}")
    print(f"[DEBUG] Parameters:")
    for key, value in params.items():
        print(f"[DEBUG]   {key}: {value}")
    print(f"[DEBUG] =========================\n")

    try:
        response = requests.get(url, headers=headers, params=params)

        # DEBUG: 打印响应状态
        print(f"[DEBUG] Response Status Code: {response.status_code}")
        print(f"[DEBUG] Response URL: {response.url}")

        if not response.ok:
            print(f"[DEBUG] Error Response: {response.text}")

        response.raise_for_status() # 检查HTTP错误
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Jira data: {e}")
        print(f"[DEBUG] Request failed with exception: {type(e).__name__}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"[DEBUG] Response text: {e.response.text}")
        return None

def calculate_state_durations(issue):
    """
    计算每个issue在各个状态下停留的时间和次数。
    返回一个字典，包含每个状态的总时间（秒）和出现次数。
    """
    issue_key = issue.get('key', 'unknown')
    state_stats = {}

    # 获取changelog
    changelog = issue.get('changelog', {})
    histories = changelog.get('histories', [])

    # 获取创建时间和当前状态
    created_str = issue['fields'].get('created')
    current_status = issue['fields'].get('status', {}).get('name', 'Unknown')
    resolution_str = issue['fields'].get('resolutiondate')

    if not created_str:
        return {}

    try:
        created_date = datetime.strptime(created_str, '%Y-%m-%dT%H:%M:%S.%f%z')
    except ValueError:
        try:
            created_date = datetime.strptime(created_str, '%Y-%m-%dT%H:%M:%S%z')
        except ValueError:
            return {}

    # 构建状态转换历史
    status_transitions = []

    # 找出所有状态变更
    for history in histories:
        history_created = history.get('created')
        if not history_created:
            continue

        try:
            transition_date = datetime.strptime(history_created, '%Y-%m-%dT%H:%M:%S.%f%z')
        except ValueError:
            try:
                transition_date = datetime.strptime(history_created, '%Y-%m-%dT%H:%M:%S%z')
            except ValueError:
                continue

        for item in history.get('items', []):
            if item.get('field') == 'status':
                from_status = item.get('fromString')
                to_status = item.get('toString')
                status_transitions.append({
                    'date': transition_date,
                    'from': from_status,
                    'to': to_status
                })

    # 按时间排序
    status_transitions.sort(key=lambda x: x['date'])

    # 确定初始状态（第一次转换的from状态，或者如果没有转换则是当前状态）
    if status_transitions:
        initial_status = status_transitions[0]['from']
    else:
        initial_status = current_status

    # 计算每个状态的停留时间
    current_state = initial_status
    current_state_start = created_date

    # 初始化第一个状态
    if current_state:
        if current_state not in state_stats:
            state_stats[current_state] = {'total_seconds': 0, 'count': 0}
        state_stats[current_state]['count'] += 1

    # 处理所有状态转换
    for transition in status_transitions:
        if current_state:
            duration = (transition['date'] - current_state_start).total_seconds()
            state_stats[current_state]['total_seconds'] += duration

        current_state = transition['to']
        current_state_start = transition['date']

        # 记录新状态
        if current_state not in state_stats:
            state_stats[current_state] = {'total_seconds': 0, 'count': 0}
        state_stats[current_state]['count'] += 1

    # 计算最后一个状态的时间（到解决时间或当前时间）
    if current_state:
        if resolution_str:
            try:
                end_date = datetime.strptime(resolution_str, '%Y-%m-%dT%H:%M:%S.%f%z')
            except ValueError:
                try:
                    end_date = datetime.strptime(resolution_str, '%Y-%m-%dT%H:%M:%S%z')
                except ValueError:
                    end_date = datetime.now(current_state_start.tzinfo)
        else:
            end_date = datetime.now(current_state_start.tzinfo)

        duration = (end_date - current_state_start).total_seconds()
        state_stats[current_state]['total_seconds'] += duration

    return state_stats

# --- 解析命令行参数 ---
parser = argparse.ArgumentParser(description='分析Jira问题的状态转换和关闭时间')
parser.add_argument('--start', type=str, help='开始日期 (格式: YYYY-MM-DD)', required=False, default=None)
parser.add_argument('--end', type=str, help='结束日期 (格式: YYYY-MM-DD)', required=False, default=None)
parser.add_argument('--status', type=str, help='问题状态 (默认: Done)', default='Done')
parser.add_argument('--project', type=str, help='项目Key (覆盖配置中的PROJECT_KEY)', default=None)
parser.add_argument('--assignee', type=str, help='指定分配人 (Assignee的用户名或邮箱)', default=None)

args = parser.parse_args()

# 使用命令行参数或配置文件中的值
project_key = args.project if args.project else PROJECT_KEY

def convert_date_to_jql(date_str):
    """
    将YYYY-MM-DD格式的日期转换为Jira JQL相对时间表达式
    比如：2024-01-15 -> "-300d" (如果是300天前)
    """
    if not date_str:
        return None

    try:
        input_date = datetime.strptime(date_str, '%Y-%m-%d')
        today = datetime.now()

        # 计算天数差异
        days_diff = (today - input_date).days

        if days_diff == 0:
            return "startOfDay()"
        elif days_diff > 0:
            # 过去的日期，使用 -Xd 格式
            return f'"-{days_diff}d"'
        else:
            # 未来的日期（虽然不太常见）
            return f'"{abs(days_diff)}d"'
    except ValueError:
        # 如果格式不对，直接返回原字符串
        return f'"{date_str}"'

# 构建JQL查询
jql_parts = [f'project = "{project_key}"']

# 添加assignee过滤
if args.assignee:
    jql_parts.append(f'assignee = "{args.assignee}"')
    print(f"过滤分配人: {args.assignee}")

# 使用resolved字段（已解决日期）来过滤已完成的任务
# 注意: 如果指定了resolved日期过滤，则不需要再指定status，因为有resolved日期的问题一定是已解决的
if args.start or args.end:
    # 有resolved日期过滤时，不添加status条件
    if args.start:
        start_jql = convert_date_to_jql(args.start)
        jql_parts.append(f'resolved >= {start_jql}')
        print(f"开始日期 {args.start} 转换为: {start_jql}")

    if args.end:
        end_jql = convert_date_to_jql(args.end)
        jql_parts.append(f'resolved <= {end_jql}')
        print(f"结束日期 {args.end} 转换为: {end_jql}")
else:
    # 没有resolved日期过滤时，才使用status参数
    if args.status:
        jql_parts.append(f'status = "{args.status}"')

JQL_DONE_ISSUES = ' AND '.join(jql_parts)

print(f"\n使用的JQL查询: {JQL_DONE_ISSUES}\n")

# 第一次请求获取总数
initial_data = fetch_jira_data(JQL_DONE_ISSUES, max_results=1)
total_issues = initial_data.get('total', 0) if initial_data else 0

# 循环拉取所有数据，然后计算时间差 (resolutiondate - created)
all_issues = []
batch_size = 50

print(f"Total issues found for analysis: {total_issues}")

if total_issues > 0:
    for start_at in range(0, total_issues, batch_size):
        print(f"Fetching issues {start_at} to {min(start_at + batch_size, total_issues)}...")
        # 添加changelog扩展以获取状态转换历史
        data = fetch_jira_data(JQL_DONE_ISSUES, start_at=start_at, max_results=batch_size, expand='changelog')
        if data and 'issues' in data:
            all_issues.extend(data['issues'])
        else:
            print(f"Failed to fetch batch starting at {start_at}")
            break

    # 收集数据概览信息
    closing_times = []
    created_dates = []
    resolution_dates = []
    issue_types = {}

    for issue in all_issues:
        try:
            created_str = issue['fields'].get('created')
            resolution_str = issue['fields'].get('resolutiondate')
            issue_type = issue['fields'].get('issuetype', {}).get('name', 'Unknown')

            # 统计issue类型
            if issue_type not in issue_types:
                issue_types[issue_type] = 0
            issue_types[issue_type] += 1

            if created_str and resolution_str:
                created_date = datetime.strptime(created_str, '%Y-%m-%dT%H:%M:%S.%f%z')
                resolution_date = datetime.strptime(resolution_str, '%Y-%m-%dT%H:%M:%S.%f%z')

                created_dates.append(created_date)
                resolution_dates.append(resolution_date)

                time_diff = (resolution_date - created_date).total_seconds()
                closing_times.append(time_diff)
        except Exception as e:
            print(f"Error processing issue {issue.get('key', 'unknown')}: {e}")

    # 开始生成报告内容
    report_lines = []
    report_lines.append("=" * 100)
    if args.assignee:
        report_lines.append(f"JIRA 数据分析报告 - {args.assignee}")
    else:
        report_lines.append("JIRA 数据分析报告")
    report_lines.append("=" * 100)
    report_lines.append(f"\n生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"项目: {project_key}")
    if args.assignee:
        report_lines.append(f"分配人: {args.assignee}")
    report_lines.append(f"JQL查询: {JQL_DONE_ISSUES}\n")

    # 数据时间范围
    report_lines.append("\n--- 数据时间范围 ---")
    if created_dates and resolution_dates:
        earliest_created = min(created_dates)
        latest_created = max(created_dates)
        earliest_resolved = min(resolution_dates)
        latest_resolved = max(resolution_dates)

        report_lines.append(f"最早创建时间: {earliest_created.strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"最晚创建时间: {latest_created.strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"最早解决时间: {earliest_resolved.strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"最晚解决时间: {latest_resolved.strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"数据跨度: {(latest_resolved - earliest_created).days} 天")

    # Issue类型统计
    report_lines.append("\n--- Issue 类型统计 ---")
    report_lines.append(f"总计: {len(all_issues)} 个issues")
    sorted_types = sorted(issue_types.items(), key=lambda x: x[1], reverse=True)
    for issue_type, count in sorted_types:
        percentage = (count / len(all_issues)) * 100
        report_lines.append(f"  {issue_type:<20} {count:>5} ({percentage:>5.1f}%)")

    if closing_times:
        avg_closing_time_seconds = sum(closing_times) / len(closing_times)
        avg_closing_time_days = avg_closing_time_seconds / (24 * 3600)
        avg_closing_time_hours = avg_closing_time_seconds / 3600

        # 计算最小和最大值
        min_time_days = min(closing_times) / (24 * 3600)
        max_time_days = max(closing_times) / (24 * 3600)

        report_lines.append("\n--- 任务关闭时间统计 ---")
        report_lines.append(f"成功分析的问题数: {len(closing_times)}")
        report_lines.append(f"平均关闭时间: {avg_closing_time_days:.2f} 天 ({avg_closing_time_hours:.2f} 小时)")
        report_lines.append(f"最短关闭时间: {min_time_days:.2f} 天")
        report_lines.append(f"最长关闭时间: {max_time_days:.2f} 天")
    else:
        report_lines.append("\nNo valid closing time data found.")

    # 分析状态停留时间
    report_lines.append("\n--- 状态停留时间分析 ---")
    all_states_aggregated = {}

    for issue in all_issues:
        issue_key = issue.get('key', 'unknown')
        state_stats = calculate_state_durations(issue)

        # 汇总所有issue的状态数据
        for state, stats in state_stats.items():
            if state not in all_states_aggregated:
                all_states_aggregated[state] = {
                    'total_seconds': 0,
                    'total_count': 0,
                    'issue_count': 0  # 有多少个issue经历过这个状态
                }
            all_states_aggregated[state]['total_seconds'] += stats['total_seconds']
            all_states_aggregated[state]['total_count'] += stats['count']
            all_states_aggregated[state]['issue_count'] += 1

    if all_states_aggregated:
        # 按平均停留时间排序
        sorted_states = sorted(all_states_aggregated.items(),
                              key=lambda x: x[1]['total_seconds'] / x[1]['issue_count'],
                              reverse=True)

        report_lines.append(f"\n分析了 {len(all_issues)} 个issues的状态转换")
        report_lines.append(f"\n{'状态':<20} {'出现次数':<12} {'经历的Issue数':<15} {'平均停留时间':<20} {'总停留时间':<20}")
        report_lines.append("=" * 100)

        for state, stats in sorted_states:
            avg_seconds = stats['total_seconds'] / stats['issue_count']
            avg_days = avg_seconds / (24 * 3600)
            avg_hours = avg_seconds / 3600
            total_days = stats['total_seconds'] / (24 * 3600)
            total_hours = stats['total_seconds'] / 3600

            # 格式化时间显示
            if avg_days >= 1:
                avg_time_str = f"{avg_days:.2f} 天"
            else:
                avg_time_str = f"{avg_hours:.2f} 小时"

            if total_days >= 1:
                total_time_str = f"{total_days:.2f} 天"
            else:
                total_time_str = f"{total_hours:.2f} 小时"

            report_lines.append(f"{state:<20} {stats['total_count']:<12} {stats['issue_count']:<15} {avg_time_str:<20} {total_time_str:<20}")

        # 输出详细的状态转换分析
        report_lines.append(f"\n--- 详细状态分析 ---")
        for state, stats in sorted_states:
            avg_transitions = stats['total_count'] / stats['issue_count']
            report_lines.append(f"\n{state}:")
            report_lines.append(f"  - {stats['issue_count']} 个issues经历过此状态")
            report_lines.append(f"  - 平均每个issue进入此状态 {avg_transitions:.2f} 次")
            if avg_transitions > 1.5:
                report_lines.append(f"  ⚠️  注意: 此状态被多次进入，可能存在来回切换的情况")
    else:
        report_lines.append("无法获取状态转换数据")

    # 打印所有报告到控制台
    for line in report_lines:
        print(line)

    # 保存报告到文本文件
    # 创建输出目录
    import os
    output_dir = 'reports'
    os.makedirs(output_dir, exist_ok=True)

    if args.assignee:
        # 只使用用户名部分（@之前的部分）作为文件名
        username = args.assignee.split('@')[0]
        report_filename = os.path.join(output_dir, f'jira_report_{username}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt')
    else:
        report_filename = os.path.join(output_dir, f'jira_report_general_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt')

    try:
        with open(report_filename, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report_lines))
        print(f"\n报告已保存到: {report_filename}")
    except Exception as e:
        print(f"\n保存报告时出错: {e}")
else:
    print("No issues found matching the criteria.")

# --- 示例：计算Velocity (需要从Sprint数据中提取，可能需要Jira Software API的特定端点) ---
# Velocity的获取通常需要特定的Jira Software API，比通用搜索复杂，可能需要特定权限。
print("\n--- Velocity计算 (基于Story Points) ---")
# 获取已完成的Story，并统计Story Points
jql_stories_parts = [f'project = "{project_key}"', 'issuetype = Story']

if args.start:
    start_jql = convert_date_to_jql(args.start)
    jql_stories_parts.append(f'resolved >= {start_jql}')

if args.end:
    end_jql = convert_date_to_jql(args.end)
    jql_stories_parts.append(f'resolved <= {end_jql}')

JQL_STORIES = ' AND '.join(jql_stories_parts)

print(f"\n[DEBUG] Story query JQL: {JQL_STORIES}\n")

story_data = fetch_jira_data(JQL_STORIES, max_results=1)
total_stories = story_data.get('total', 0) if story_data else 0

if total_stories > 0:
    all_stories = []
    for start_at in range(0, total_stories, batch_size):
        data = fetch_jira_data(JQL_STORIES, start_at=start_at, max_results=batch_size, expand='changelog')
        if data and 'issues' in data:
            all_stories.extend(data['issues'])

    # 尝试提取Story Points（字段名可能因配置而异，常见的有customfield_xxxxx）
    # 你需要检查你的Jira实例中Story Points的字段名
    total_story_points = 0
    stories_with_points = 0

    for story in all_stories:
        story_points = story['fields'].get('customfield_12310243')
        if story_points:
            total_story_points += float(story_points)
            stories_with_points += 1

    print(f"已完成的Stories数量: {total_stories}")
    print(f"包含Story Points的Stories: {stories_with_points}")
    print(f"总Story Points: {total_story_points}")
    if stories_with_points > 0:
        print(f"平均每个Story的Points: {total_story_points / stories_with_points:.2f}")
else:
    print("No stories found matching the criteria.")

# --- 保存分析结果到JSON文件 ---
print("\n--- 保存分析结果 ---")
try:
    output_data = {
        'analysis_date': datetime.now().isoformat(),
        'project_key': project_key,
        'query_parameters': {
            'start_date': args.start,
            'end_date': args.end,
            'status': args.status,
        },
        'jql_query': JQL_DONE_ISSUES,
        'total_issues_analyzed': len(all_issues) if 'all_issues' in locals() else 0,
        'closing_time_stats': {
            'average_days': avg_closing_time_days if 'avg_closing_time_days' in locals() else None,
            'average_hours': avg_closing_time_hours if 'avg_closing_time_hours' in locals() else None,
            'min_days': min_time_days if 'min_time_days' in locals() else None,
            'max_days': max_time_days if 'max_time_days' in locals() else None,
        },
        'state_statistics': {},
        'velocity_stats': {
            'total_stories': total_stories if 'total_stories' in locals() else 0,
            'total_story_points': total_story_points if 'total_story_points' in locals() else 0,
            'stories_with_points': stories_with_points if 'stories_with_points' in locals() else 0,
        }
    }

    # 添加状态统计
    if 'all_states_aggregated' in locals():
        for state, stats in all_states_aggregated.items():
            avg_seconds = stats['total_seconds'] / stats['issue_count']
            output_data['state_statistics'][state] = {
                'total_count': stats['total_count'],
                'issue_count': stats['issue_count'],
                'average_seconds': avg_seconds,
                'average_days': avg_seconds / (24 * 3600),
                'average_hours': avg_seconds / 3600,
                'total_seconds': stats['total_seconds'],
                'avg_transitions_per_issue': stats['total_count'] / stats['issue_count']
            }

    output_filename = f'jira_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"分析结果已保存到: {output_filename}")
except Exception as e:
    print(f"保存结果时出错: {e}")
