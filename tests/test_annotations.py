from src.registry import load_tools, registry
load_tools()

def test_all_tools_have_annotations():
    tools = registry.list_tools()
    assert len(tools) == 16
    for t in tools:
        assert t.annotations, f'{t.name} 缺少 annotations'
        assert 'readOnlyHint' in t.annotations or 'destructiveHint' in t.annotations, \
            f'{t.name} 未声明 readOnlyHint 或 destructiveHint'

def test_readonly_tools():
    readonly = {
        'read_file',
        'read_file_lines',
        'get_file_info',
        'list_dir',
        'search_text',
        'get_task_status',
        'list_tasks',
        'find_process',
        'get_device_status',
    }
    for t in registry.list_tools():
        if t.name in readonly:
            assert t.annotations.get('readOnlyHint') is True, \
                f'{t.name} 应为 readOnly'

def test_destructive_tools():
    destructive = {
        'run_command',
        'run_background_command',
        'edit_file',
        'manage_file',
        'cancel_task',
        'kill_process',
    }
    for t in registry.list_tools():
        if t.name in destructive:
            assert t.annotations.get('destructiveHint') is True, \
                f'{t.name} 应为 destructive'

def test_run_command_strong_reminder():
    tool = registry.get_tool('run_command')
    assert tool is not None
    assert '仅供用于工具做不到的时候使用' in tool.description
    assert 'CRITICAL' in tool.description

def test_tool_descriptions_are_detailed_and_actionable():
    for t in registry.list_tools():
        assert len(t.description.strip()) >= 50, f'{t.name} 的描述过短，未达到详细实用指引标准'

def test_aliases_backward_compatible():
    assert registry.get_tool('read_files') == registry.get_tool('read_file')
    assert registry.get_tool('search_texts') == registry.get_tool('search_text')
    assert registry.get_tool('file_info') == registry.get_tool('get_file_info')
    assert registry.get_tool('start_task') == registry.get_tool('run_command')
    assert registry.get_tool('start_task_for_backend') == registry.get_tool('run_background_command')

