from src.registry import load_tools, registry
load_tools()

def test_all_tools_have_annotations():
    tools = registry.list_tools()
    assert len(tools) > 0
    for t in tools:
        assert t.annotations, f'{t.name} 缺少 annotations'
        assert 'readOnlyHint' in t.annotations or 'destructiveHint' in t.annotations, \
            f'{t.name} 未声明 readOnlyHint 或 destructiveHint'

def test_readonly_tools():
    readonly = {'get_files', 'list_dir', 'search_texts',
                'get_task_status', 'list_tasks'}
    for t in registry.list_tools():
        if t.name in readonly:
            assert t.annotations.get('readOnlyHint') is True, \
                f'{t.name} 应为 readOnly'

def test_destructive_tools():
    destructive = {'start_task', 'cancel_task'}
    for t in registry.list_tools():
        if t.name in destructive:
            assert t.annotations.get('destructiveHint') is True, \
                f'{t.name} 应为 destructive'
