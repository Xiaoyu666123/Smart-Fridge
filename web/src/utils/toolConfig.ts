export const toolNameLabels: Record<string, string> = {
  vision_recognize: '视觉识别',
  vision_assist_decide: '识别策略决策',
  llm_freshness: '保鲜期推算',
  db_write_inventory: '写入库存',
  db_write_event_log: '写入事件日志',
  db_query_inventory: '查询库存',
  preference_extract: '偏好提取',
  db_save_preferences: '保存偏好',
  llm_recipe: '食谱推荐',
  llm_recipe_stream: '食谱推荐(流式)',
  llm_recipe_struct_stream: '结构化食谱推荐',
  db_save_conversation: '保存对话',
  embedding_extract: '向量提取',
  vector_dedup: '向量去重',
  label_associate: '标签关联',
  weather_query: '天气查询',
  trace_explain: 'AI 决策解释',
}

export const toolIcons: Record<string, string> = {
  vision_recognize: 'Camera',
  vision_assist_decide: 'Aim',
  llm_freshness: 'Timer',
  db_write_inventory: 'FolderAdd',
  db_write_event_log: 'Document',
  db_query_inventory: 'Search',
  preference_extract: 'MagicStick',
  db_save_preferences: 'Stamp',
  llm_recipe: 'Food',
  llm_recipe_stream: 'Food',
  llm_recipe_struct_stream: 'Food',
  db_save_conversation: 'ChatLineSquare',
  embedding_extract: 'Grid',
  vector_dedup: 'Filter',
  label_associate: 'CollectionTag',
  weather_query: 'Sunny',
  trace_explain: 'MagicStick',
}

/**
 * 每个工具的"人话说明"——一句话讲清楚这一步在干什么，
 * 给非技术观众看懂工具链。
 */
export const toolDescriptions: Record<string, string> = {
  vision_recognize: '把食材照片发给云端多模态大模型，识别出这是什么食材',
  vision_assist_decide: '根据端侧置信度判断是否需要调用云端复核（落在触发区间才调）',
  llm_freshness: '让大模型结合食材种类、城市、季节推算还能放多少天',
  db_write_inventory: '把这件食材正式写入库存表',
  db_write_event_log: '记录一条出入库流水，留作审计与统计',
  db_query_inventory: '从数据库读出当前冰箱里的库存清单',
  preference_extract: '从用户这句话里提取口味/忌口等偏好',
  db_save_preferences: '把提取到的偏好存进数据库，下次推荐更懂你',
  llm_recipe: '综合库存、偏好、天气，让大模型生成食谱推荐',
  llm_recipe_stream: '综合库存、偏好、天气，流式生成食谱推荐',
  llm_recipe_struct_stream: '生成结构化食谱卡片（含食材、步骤、标签）',
  db_save_conversation: '把这轮对话存进历史，方便下次理解上下文',
  embedding_extract: '把食材图片转成 1024 维特征向量，用于身份识别',
  vector_dedup: '拿特征向量和已有库存比对，判断是不是同一件物品（防重复入库）',
  label_associate: '把之前扫到的包装标签（品牌、保质期）关联到这件食材',
  weather_query: '查询当前城市天气，让推荐更应景（如高温推荐清淡菜）',
  trace_explain: '让大模型把整条工具链翻译成一段人话解释',
}

/**
 * 工具大类（用于时间线左侧分组着色与图例）。
 */
export interface ToolCategory {
  key: string
  label: string
  color: string
}

export const toolCategoryMap: Record<string, ToolCategory> = {
  vision_recognize: { key: 'ai', label: 'AI 推理', color: '#722ed1' },
  vision_assist_decide: { key: 'ai', label: 'AI 推理', color: '#722ed1' },
  llm_freshness: { key: 'ai', label: 'AI 推理', color: '#722ed1' },
  preference_extract: { key: 'ai', label: 'AI 推理', color: '#722ed1' },
  llm_recipe: { key: 'ai', label: 'AI 推理', color: '#722ed1' },
  llm_recipe_stream: { key: 'ai', label: 'AI 推理', color: '#722ed1' },
  llm_recipe_struct_stream: { key: 'ai', label: 'AI 推理', color: '#722ed1' },
  trace_explain: { key: 'ai', label: 'AI 推理', color: '#722ed1' },
  db_write_inventory: { key: 'db', label: '数据库', color: '#0ea5e9' },
  db_write_event_log: { key: 'db', label: '数据库', color: '#0ea5e9' },
  db_query_inventory: { key: 'db', label: '数据库', color: '#0ea5e9' },
  db_save_preferences: { key: 'db', label: '数据库', color: '#0ea5e9' },
  db_save_conversation: { key: 'db', label: '数据库', color: '#0ea5e9' },
  label_associate: { key: 'db', label: '数据库', color: '#0ea5e9' },
  embedding_extract: { key: 'vector', label: '向量计算', color: '#0fc6c2' },
  vector_dedup: { key: 'vector', label: '向量计算', color: '#0fc6c2' },
  weather_query: { key: 'api', label: '外部 API', color: '#ff7d00' },
}

export function getToolCategory(toolName: string): ToolCategory {
  return toolCategoryMap[toolName] || { key: 'other', label: '其它', color: '#86909c' }
}


/**
 * 工具 emoji（用于 Canvas 2D 直接 fillText 绘制图标）。
 */
export const toolEmojis: Record<string, string> = {
  vision_recognize: '📷',
  vision_assist_decide: '🎯',
  llm_freshness: '⏳',
  db_write_inventory: '📥',
  db_write_event_log: '📝',
  db_query_inventory: '🔍',
  preference_extract: '✨',
  db_save_preferences: '💾',
  llm_recipe: '🍳',
  llm_recipe_stream: '🍳',
  llm_recipe_struct_stream: '🍱',
  db_save_conversation: '💬',
  embedding_extract: '🧬',
  vector_dedup: '🔁',
  label_associate: '🏷️',
  weather_query: '🌤️',
  trace_explain: '🧠',
}

export function getToolEmoji(name: string): string {
  return toolEmojis[name] || '⚙️'
}
