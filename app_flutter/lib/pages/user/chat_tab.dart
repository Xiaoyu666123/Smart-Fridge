import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/theme.dart';
import '../../core/auth_store.dart';
import '../../core/dio_client.dart';
import '../../api/user_api.dart';
import '../../api/chat_stream.dart';
import '../../models/chat_models.dart';
import 'widgets/recipe_card_widget.dart';

/// AI 食谱推荐页（原生流式对话 + 食谱卡片 + 库存问答 + 历史抽屉）。
class ChatTab extends ConsumerStatefulWidget {
  const ChatTab({super.key});

  @override
  ConsumerState<ChatTab> createState() => _ChatTabState();
}

class _ChatTabState extends ConsumerState<ChatTab> {
  final _inputCtrl = TextEditingController();
  final _scrollCtrl = ScrollController();
  final List<ChatMessage> _messages = [];
  bool _loading = false;
  String _mode = 'recipe'; // recipe | inventory
  StreamSubscription<ChatEvent>? _sub;
  final Set<String> _savedNames = {};

  // 历史
  List<Map<String, dynamic>> _history = [];

  static const _recipePrompts = [
    ('⏰', '清临期', '请用我冰箱里最快过期的食材，给我推荐 2 道菜，要简单快手。'),
    ('🌟', '今日推荐', '看看我冰箱里有什么，根据当前天气和季节，推荐一道适合今天的菜。'),
    ('🥗', '清淡少油', '用我冰箱里的食材，推荐 1 道清淡少油的菜。'),
    ('🍳', '15分钟', '用我冰箱里的食材，推荐 2 道 15 分钟内就能做好的快手菜。'),
  ];
  static const _invPrompts = [
    ('⏰', '快过期的', '我有哪些 3 天内要过期的食材？'),
    ('🥩', '还有肉吗', '冰箱里还有哪些肉类或蛋白质？'),
    ('🥬', '蔬菜清单', '我现在有哪些蔬菜？'),
    ('🔢', '一共多少', '我冰箱里现在一共有多少件食材？都有什么？'),
  ];

  @override
  void initState() {
    super.initState();
    _loadSaved();
    _loadHistory();
  }

  @override
  void dispose() {
    _sub?.cancel();
    _inputCtrl.dispose();
    _scrollCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadSaved() async {
    try {
      final list = await ref.read(userApiProvider).savedRecipes(limit: 100);
      if (mounted) {
        setState(() {
          _savedNames.addAll(list.map((e) => (e['name'] ?? '').toString()));
        });
      }
    } catch (_) {}
  }

  Future<void> _loadHistory() async {
    try {
      final list = await ref.read(userApiProvider).conversations();
      if (mounted) setState(() => _history = list);
    } catch (_) {}
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollCtrl.hasClients) {
        _scrollCtrl.jumpTo(_scrollCtrl.position.maxScrollExtent);
      }
    });
  }

  Future<void> _send([String? preset]) async {
    final text = (preset ?? _inputCtrl.text).trim();
    if (text.isEmpty || _loading) return;
    _inputCtrl.clear();

    setState(() {
      _messages.add(ChatMessage(role: 'user', content: text));
      _loading = true;
    });
    _scrollToBottom();

    if (_mode == 'inventory') {
      await _sendInventory(text);
    } else {
      await _sendRecipe(text);
    }
  }

  Future<void> _sendRecipe(String text) async {
    final placeholder = ChatMessage(role: 'assistant', structured: true);
    setState(() => _messages.add(placeholder));
    final idx = _messages.length - 1;
    final token = ref.read(authProvider).userToken;

    _sub = ChatStream.stream(message: text, token: token, structured: true)
        .listen((ev) {
      if (!mounted) return;
      final cur = _messages[idx];
      if (ev.type == ChatEventType.delta) {
        cur.parseBuffer += ev.content;
        cur.parseRecipeBuffer();
        setState(() {});
        _scrollToBottom();
      } else if (ev.type == ChatEventType.done) {
        cur.parseRecipeBuffer();
        setState(() => _loading = false);
        _loadHistory();
      } else if (ev.type == ChatEventType.error) {
        if (cur.content.isEmpty && cur.recipes.isEmpty) {
          cur.content = '抱歉，推荐服务暂时不可用，请稍后再试。';
        }
        setState(() => _loading = false);
      }
    }, onError: (e) {
      if (!mounted) return;
      final cur = _messages[idx];
      if (cur.content.isEmpty && cur.recipes.isEmpty) {
        cur.content = '连接中断，请稍后再试。';
      }
      setState(() => _loading = false);
    }, onDone: () {
      if (mounted && _loading) setState(() => _loading = false);
    });
  }

  Future<void> _sendInventory(String text) async {
    final placeholder = ChatMessage(role: 'assistant', kind: 'inventory');
    setState(() => _messages.add(placeholder));
    final idx = _messages.length - 1;
    try {
      final res = await ref.read(userApiProvider).inventoryQuery(text);
      if (!mounted) return;
      _messages[idx].content = (res['answer'] ?? '').toString();
      _messages[idx].invMatched =
          (res['matched'] as List?)?.map((e) => e.toString()).toList() ?? [];
    } catch (e) {
      if (!mounted) return;
      _messages[idx].content = extractError(e, '库存查询暂时不可用，请稍后再试。');
    } finally {
      if (mounted) setState(() => _loading = false);
      _scrollToBottom();
    }
  }

  Future<void> _saveRecipe(RecipeCard r) async {
    try {
      await ref.read(userApiProvider).saveRecipe(r.toJson());
      if (mounted) {
        setState(() => _savedNames.add(r.name));
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text('已收藏「${r.name}」'),
          backgroundColor: AppColors.success,
          behavior: SnackBarBehavior.floating,
        ));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(extractError(e, '收藏失败')),
          backgroundColor: AppColors.danger,
          behavior: SnackBarBehavior.floating,
        ));
      }
    }
  }

  void _newChat() {
    _sub?.cancel();
    setState(() {
      _messages.clear();
      _loading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bgColor,
      appBar: AppBar(
        leading: Builder(
          builder: (ctx) => IconButton(
            icon: const Icon(Icons.menu),
            onPressed: () => Scaffold.of(ctx).openDrawer(),
          ),
        ),
        title: GestureDetector(
          onTap: () => setState(
              () => _mode = _mode == 'recipe' ? 'inventory' : 'recipe'),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(_mode == 'recipe' ? 'AI 食谱推荐' : '问库存'),
              const SizedBox(width: 4),
              const Icon(Icons.swap_horiz, size: 18),
            ],
          ),
        ),
        actions: [
          IconButton(
              icon: const Icon(Icons.add_comment_outlined),
              onPressed: _newChat),
        ],
      ),
      drawer: _historyDrawer(),
      body: Column(
        children: [
          Expanded(
            child: _messages.isEmpty
                ? _emptyState()
                : ListView.builder(
                    controller: _scrollCtrl,
                    padding: const EdgeInsets.all(14),
                    itemCount: _messages.length + (_loading ? 1 : 0),
                    itemBuilder: (c, i) {
                      if (i >= _messages.length) return _typingBubble();
                      return _messageWidget(_messages[i]);
                    },
                  ),
          ),
          _inputDock(),
        ],
      ),
    );
  }

  // ---- 空态 ----
  Widget _emptyState() {
    final username = ref.watch(authProvider).username;
    final prompts = _mode == 'recipe' ? _recipePrompts : _invPrompts;
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        const SizedBox(height: 40),
        Center(
          child: Container(
            width: 64,
            height: 64,
            decoration: BoxDecoration(
              gradient: const LinearGradient(colors: [
                AppColors.brandPrimaryHover,
                AppColors.brandPrimaryDark
              ]),
              borderRadius: BorderRadius.circular(20),
            ),
            child: const Icon(Icons.auto_awesome, color: Colors.white, size: 30),
          ),
        ),
        const SizedBox(height: 16),
        Center(
          child: Text('嗨，$username 👋',
              style: const TextStyle(
                  fontSize: 22, fontWeight: FontWeight.w700)),
        ),
        const SizedBox(height: 8),
        Center(
          child: Text(
            _mode == 'recipe'
                ? '我能根据你的库存和口味，帮你想今天吃什么'
                : '问问冰箱里有什么、什么快过期了',
            textAlign: TextAlign.center,
            style: const TextStyle(color: AppColors.textSecondary, height: 1.5),
          ),
        ),
        const SizedBox(height: 26),
        ...prompts.map((p) => Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: InkWell(
                onTap: () => _send(p.$3),
                borderRadius: BorderRadius.circular(14),
                child: Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: AppColors.bgCard,
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: AppColors.borderColor),
                  ),
                  child: Row(
                    children: [
                      Text(p.$1, style: const TextStyle(fontSize: 22)),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(p.$2,
                                style: const TextStyle(
                                    fontSize: 15, fontWeight: FontWeight.w600)),
                            const SizedBox(height: 2),
                            Text(p.$3,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(
                                    fontSize: 12,
                                    color: AppColors.textPlaceholder)),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            )),
      ],
    );
  }

  // ---- 消息 ----
  Widget _messageWidget(ChatMessage msg) {
    if (msg.role == 'user') {
      return Align(
        alignment: Alignment.centerRight,
        child: Container(
          margin: const EdgeInsets.only(bottom: 12, left: 40),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          decoration: BoxDecoration(
            gradient: const LinearGradient(colors: [
              AppColors.brandPrimary,
              AppColors.brandPrimaryDark
            ]),
            borderRadius: const BorderRadius.only(
              topLeft: Radius.circular(18),
              topRight: Radius.circular(18),
              bottomLeft: Radius.circular(18),
              bottomRight: Radius.circular(4),
            ),
          ),
          child: Text(msg.content,
              style: const TextStyle(
                  color: Colors.white, fontSize: 15, height: 1.5)),
        ),
      );
    }
    // assistant
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 30,
            height: 30,
            decoration: BoxDecoration(
              gradient: const LinearGradient(colors: [
                AppColors.brandPrimaryHover,
                AppColors.brandPrimaryDark
              ]),
              borderRadius: BorderRadius.circular(9),
            ),
            child: const Icon(Icons.smart_toy, color: Colors.white, size: 16),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (msg.content.isNotEmpty)
                  Text(msg.content,
                      style: const TextStyle(fontSize: 15, height: 1.7)),
                // 库存命中标签
                if (msg.kind == 'inventory' && msg.invMatched.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Wrap(
                      spacing: 6,
                      runSpacing: 6,
                      children: msg.invMatched
                          .map((c) => Container(
                                padding: const EdgeInsets.symmetric(
                                    horizontal: 10, vertical: 3),
                                decoration: BoxDecoration(
                                  color: AppColors.brandPrimaryLight,
                                  borderRadius: BorderRadius.circular(999),
                                ),
                                child: Text(c,
                                    style: const TextStyle(
                                        fontSize: 12,
                                        color: AppColors.brandPrimaryDark)),
                              ))
                          .toList(),
                    ),
                  ),
                // 食谱卡片
                ...msg.recipes.map((r) => RecipeCardWidget(
                      recipe: r,
                      saved: _savedNames.contains(r.name),
                      onSave: () => _saveRecipe(r),
                    )),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _typingBubble() {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 30,
            height: 30,
            decoration: BoxDecoration(
              gradient: const LinearGradient(colors: [
                AppColors.brandPrimaryHover,
                AppColors.brandPrimaryDark
              ]),
              borderRadius: BorderRadius.circular(9),
            ),
            child: const Icon(Icons.smart_toy, color: Colors.white, size: 16),
          ),
          const SizedBox(width: 10),
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: AppColors.bgCard,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: AppColors.borderColor),
            ),
            child: const SizedBox(
              width: 36,
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  _Dot(), _Dot(), _Dot(),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ---- 输入条 ----
  Widget _inputDock() {
    return Container(
      padding: EdgeInsets.fromLTRB(
          12, 8, 12, 8 + MediaQuery.of(context).padding.bottom),
      decoration: const BoxDecoration(
        color: AppColors.bgCard,
        border: Border(top: BorderSide(color: AppColors.borderColor)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Expanded(
            child: Container(
              decoration: BoxDecoration(
                color: AppColors.bgSoft,
                borderRadius: BorderRadius.circular(22),
                border: Border.all(color: AppColors.borderColor),
              ),
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: TextField(
                controller: _inputCtrl,
                minLines: 1,
                maxLines: 4,
                textInputAction: TextInputAction.send,
                onSubmitted: (_) => _send(),
                decoration: InputDecoration(
                  border: InputBorder.none,
                  enabledBorder: InputBorder.none,
                  focusedBorder: InputBorder.none,
                  errorBorder: InputBorder.none,
                  disabledBorder: InputBorder.none,
                  focusedErrorBorder: InputBorder.none,
                  filled: false,
                  isCollapsed: true,
                  contentPadding: const EdgeInsets.symmetric(vertical: 11),
                  hintText: _mode == 'inventory' ? '问问冰箱里有什么…' : '想吃点什么…',
                ),
              ),
            ),
          ),
          const SizedBox(width: 8),
          GestureDetector(
            onTap: _loading ? null : () => _send(),
            child: Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                gradient: _loading
                    ? null
                    : const LinearGradient(colors: [
                        AppColors.brandPrimary,
                        AppColors.brandPrimaryDark
                      ]),
                color: _loading ? AppColors.bgSoft : null,
                shape: BoxShape.circle,
              ),
              child: Icon(Icons.send,
                  color: _loading ? AppColors.textPlaceholder : Colors.white,
                  size: 20),
            ),
          ),
        ],
      ),
    );
  }

  // ---- 历史抽屉 ----
  Widget _historyDrawer() {
    // 把扁平消息按"轮次"分组（user 提问开一轮）
    final turns = <Map<String, dynamic>>[];
    Map<String, dynamic>? cur;
    for (final m in _history) {
      if (m['role'] == 'user') {
        cur = {'question': m['content'], 'time': m['created_at'], 'msgs': [m]};
        turns.add(cur);
      } else if (cur != null) {
        (cur['msgs'] as List).add(m);
      }
    }

    return Drawer(
      child: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.all(16),
              child: Row(
                children: [
                  const Text('对话记录',
                      style: TextStyle(
                          fontSize: 16, fontWeight: FontWeight.w700)),
                  const Spacer(),
                  TextButton.icon(
                    onPressed: () {
                      Navigator.pop(context);
                      _newChat();
                    },
                    icon: const Icon(Icons.add, size: 16),
                    label: const Text('新对话'),
                  ),
                ],
              ),
            ),
            const Divider(height: 1),
            Expanded(
              child: turns.isEmpty
                  ? const Center(
                      child: Text('暂无历史对话',
                          style: TextStyle(color: AppColors.textPlaceholder)))
                  : ListView.builder(
                      itemCount: turns.length,
                      itemBuilder: (c, i) {
                        final t = turns[turns.length - 1 - i]; // 新的在上
                        return ListTile(
                          leading: const Icon(Icons.chat_bubble_outline,
                              color: AppColors.brandPrimary, size: 20),
                          title: Text((t['question'] ?? '').toString(),
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(fontSize: 14)),
                          onTap: () {
                            Navigator.pop(context);
                            _loadTurn(t);
                          },
                        );
                      },
                    ),
            ),
          ],
        ),
      ),
    );
  }

  void _loadTurn(Map<String, dynamic> turn) {
    _sub?.cancel();
    final msgs = <ChatMessage>[];
    for (final m in (turn['msgs'] as List)) {
      if (m['role'] == 'user') {
        msgs.add(ChatMessage(role: 'user', content: (m['content'] ?? '').toString()));
      } else {
        final content = (m['content'] ?? '').toString();
        final cm = ChatMessage(
          role: 'assistant',
          structured: content.contains('===RECIPE==='),
          parseBuffer: content,
        );
        if (cm.structured) {
          cm.parseRecipeBuffer();
        } else {
          cm.content = content;
        }
        msgs.add(cm);
      }
    }
    setState(() {
      _messages
        ..clear()
        ..addAll(msgs);
      _loading = false;
    });
    _scrollToBottom();
  }
}

class _Dot extends StatefulWidget {
  const _Dot();
  @override
  State<_Dot> createState() => _DotState();
}

class _DotState extends State<_Dot> with SingleTickerProviderStateMixin {
  late final AnimationController _c =
      AnimationController(vsync: this, duration: const Duration(milliseconds: 600))
        ..repeat(reverse: true);

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: _c,
      child: Container(
        width: 7,
        height: 7,
        decoration: const BoxDecoration(
          color: AppColors.textPlaceholder,
          shape: BoxShape.circle,
        ),
      ),
    );
  }
}
