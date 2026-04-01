/* ===== easy_ai_search Admin — Vue 3 CDN App ===== */
const { createApp, ref, reactive, computed, watch, onMounted, nextTick } = Vue

// ── API 封装 ──
const apiKey = ref(localStorage.getItem('opensearch_api_key') || '')
watch(apiKey, (val) => { localStorage.setItem('opensearch_api_key', val) })

async function api(path, opts = {}) {
  const { method = 'GET', body } = opts
  const headers = { 'X-API-Key': apiKey.value }
  if (body) headers['Content-Type'] = 'application/json'
  const res = await fetch(path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  // DELETE 可能返回空
  const text = await res.text()
  return text ? JSON.parse(text) : null
}

// ── 搜索页 ──
const SearchPage = {
  template: `
    <div>
      <div class="search-box">
        <input v-model="query" placeholder="输入搜索内容…" @keyup.enter="doSearch" />
        <button class="btn btn-primary" @click="doSearch" :disabled="loading || !query.trim()">
          {{ loading ? '搜索中…' : '搜索' }}
        </button>
      </div>
      <div class="form-row" style="margin-bottom:16px">
        <div class="form-group">
          <label>最大结果数</label>
          <input type="number" v-model.number="maxResults" min="1" max="20" />
        </div>
        <div class="form-group">
          <label>搜索预设</label>
          <select v-model="searchPreset" @change="applyPreset">
            <option value="custom">custom（手动）</option>
            <option value="general_fast">通用快速</option>
            <option value="official_news">官方新闻优先</option>
            <option value="official_only">仅限官方域名</option>
            <option value="tech_docs">技术文档优先</option>
            <option value="social_news">官方+社交时效</option>
          </select>
        </div>
        <div class="form-group">
          <label>搜索模式</label>
          <select v-model="mode">
            <option value="fast">fast（更快）</option>
            <option value="balanced">balanced（默认）</option>
            <option value="deep">deep（更完整）</option>
          </select>
        </div>
        <div class="form-group">
          <label>来源策略</label>
          <select v-model="sourceProfile">
            <option value="general">general（通用）</option>
            <option value="official_news">official_news（官方新闻优先）</option>
            <option value="social_realtime">social_realtime（社交时效优先）</option>
            <option value="official_plus_social">official_plus_social（官方+社交）</option>
            <option value="tech_community">tech_community（技术社区）</option>
          </select>
        </div>
        <div class="form-group">
          <label style="display:flex;align-items:center;gap:8px">
            <label class="toggle">
              <input type="checkbox" v-model="skipLocal" />
              <span class="slider"></span>
            </label>
            跳过本地搜索
          </label>
        </div>
        <div class="form-group">
          <label style="display:flex;align-items:center;gap:8px">
            <label class="toggle">
              <input type="checkbox" v-model="disableDeepProcess" />
              <span class="slider"></span>
            </label>
            禁用深度处理（直出全文）
          </label>
        </div>
      </div>

      <div class="card" style="margin-bottom:16px">
        <div style="font-size:13px;font-weight:600;margin-bottom:8px;color:#444">高级域名控制</div>
        <div class="form-row">
          <div class="form-group">
            <label>优先域名</label>
            <input type="text" v-model="preferredDomainsText" placeholder="openai.com, redis.io, cnblogs.com" />
          </div>
          <div class="form-group">
            <label>屏蔽域名</label>
            <input type="text" v-model="blockedDomainsText" placeholder="help.openai.com, example.com" />
          </div>
          <div class="form-group">
            <label>偏好强度</label>
            <select v-model="domainPreferenceMode">
              <option value="prefer">prefer（轻度偏好）</option>
              <option value="strong_prefer">strong_prefer（强偏好）</option>
              <option value="only">only（仅限这些域名）</option>
            </select>
          </div>
        </div>
        <div style="margin-top:6px;font-size:12px;color:#888">
          适合调试 MCP / Agent 工具行为；<code>only</code> 会严格限制结果来源。
        </div>
        <div style="margin-top:6px;font-size:12px;color:#888">
          当前预设：{{ presetDescriptions[searchPreset] }}
        </div>
        <div style="margin-top:8px" v-if="searchPreset === 'custom'">
          <label style="font-size:12px;color:#666">custom 策略名称</label>
          <input type="text" v-model="customStrategyName" placeholder="我的来源策略" />
        </div>
        <div style="margin-top:6px;font-size:12px;color:#888" v-if="hasSavedStrategy && savedStrategyName">
          已保存 custom：{{ savedStrategyName }}
        </div>
        <div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap">
          <button class="btn" @click="saveCustomStrategy">保存当前为 custom</button>
          <button class="btn" @click="loadSavedStrategy" :disabled="!hasSavedStrategy">加载已保存 custom</button>
        </div>
      </div>

      <div class="card" style="margin-bottom:16px">
        <div style="font-size:13px;font-weight:600;margin-bottom:8px;color:#444">搜索引擎</div>
        <div style="display:flex;flex-wrap:wrap;gap:8px">
          <label v-for="eng in engineOptions" :key="eng.value"
                 style="display:flex;align-items:center;gap:4px;cursor:pointer;font-size:13px;
                        padding:4px 10px;border:1px solid #d0d7de;border-radius:6px;
                        background:white;user-select:none"
                 :style="selectedEngines.includes(eng.value) ? 'background:#e8f4fd;border-color:#0969da;color:#0969da' : ''">
            <input type="checkbox" :value="eng.value" v-model="selectedEngines" style="display:none" />
            {{ eng.label }}
          </label>
        </div>
        <div style="margin-top:6px;font-size:12px;color:#888">
          {{ selectedEngines.length === 0 ? '未选择（使用所有引擎）' : '已选：' + selectedEngines.join(', ') }}
        </div>
      </div>

      <div v-if="error" class="msg msg-error">{{ error }}</div>

      <div v-if="result" class="card" style="margin-bottom:16px">
        <div style="display:flex;justify-content:space-between;font-size:13px;color:#666">
          <span>来源：<span :class="result.source==='local'?'badge badge-local':'badge badge-online'">{{ result.source }}</span></span>
          <span>耗时：{{ result.total_time.toFixed(3) }}s</span>
        </div>
      </div>

      <div v-if="result && result.results.length">
        <div class="result-item" v-for="(r, i) in result.results" :key="i">
          <div class="result-title">{{ r.title || '无标题' }}</div>
          <div class="result-url" v-if="r.url"><a :href="r.url" target="_blank">{{ r.url }}</a></div>
          <div class="result-content">{{ truncate(r.cleaned_content, 300) }}</div>
          <div class="result-meta">
            <span v-if="r.similarity_score">相似度: {{ (r.similarity_score * 100).toFixed(1) }}%</span>
            <span v-if="r.metadata && r.metadata.source">
              <span :class="r.metadata.source==='local'?'badge badge-local':'badge badge-online'">{{ r.metadata.source }}</span>
            </span>
          </div>
        </div>
      </div>
      <div v-else-if="result && !result.results.length" class="empty">无搜索结果</div>
    </div>
  `,
  setup() {
    const query = ref('')
    const maxResults = ref(5)
    const skipLocal = ref(false)
    const disableDeepProcess = ref(false)
    const searchPreset = ref('custom')
    const mode = ref('balanced')
    const sourceProfile = ref('general')
    const preferredDomainsText = ref('')
    const blockedDomainsText = ref('')
    const domainPreferenceMode = ref('prefer')
    const customStrategyName = ref('我的来源策略')
    const hasSavedStrategy = ref(false)
    const savedStrategyName = ref('')
    const loading = ref(false)
    const error = ref('')
    const result = ref(null)

    const engineOptions = [
      { value: 'bing',        label: 'Bing' },
      { value: 'baidu',       label: '百度' },
      { value: 'sogou',       label: '搜狗' },
      { value: '360search',   label: '360搜索' },
      { value: 'google',      label: 'Google' },
      { value: 'mojeek',      label: 'Mojeek' },
      { value: 'presearch',   label: 'Presearch' },
      { value: 'mwmbl',       label: 'Mwmbl' },
    ]
    const selectedEngines = ref([])
    const presetDescriptions = {
      custom: '完全手动控制当前参数。',
      general_fast: '快速模式，适合大多数普通搜索。',
      official_news: '偏向官方站和主流新闻源，适合发布信息类查询。',
      official_only: '严格只搜指定官方域名，适合验真。',
      tech_docs: '偏向官方文档与技术博客，适合技术问题。',
      social_news: '加入社交媒体来源，适合追踪更强时效性的讨论和爆料。',
    }
    const customStrategyKey = 'opensearch.search.customStrategy.v1'
    const presetValues = {
      general_fast: {
        mode: 'fast',
        sourceProfile: 'general',
        disableDeepProcess: true,
        preferredDomainsText: '',
        blockedDomainsText: '',
        domainPreferenceMode: 'prefer',
      },
      official_news: {
        mode: 'fast',
        sourceProfile: 'official_news',
        disableDeepProcess: true,
        preferredDomainsText: 'openai.com, sina.com.cn, dataconomy.com',
        blockedDomainsText: 'help.openai.com',
        domainPreferenceMode: 'strong_prefer',
      },
      official_only: {
        mode: 'fast',
        sourceProfile: 'official_news',
        disableDeepProcess: true,
        preferredDomainsText: 'openai.com',
        blockedDomainsText: 'help.openai.com',
        domainPreferenceMode: 'only',
      },
      tech_docs: {
        mode: 'fast',
        sourceProfile: 'tech_community',
        disableDeepProcess: true,
        preferredDomainsText: 'docs.python.org, redis.io, developer.mozilla.org, cnblogs.com',
        blockedDomainsText: '',
        domainPreferenceMode: 'strong_prefer',
      },
      social_news: {
        mode: 'fast',
        sourceProfile: 'official_plus_social',
        disableDeepProcess: true,
        preferredDomainsText: 'x.com, twitter.com, weibo.com, openai.com, news.qq.com',
        blockedDomainsText: 'help.openai.com',
        domainPreferenceMode: 'prefer',
      },
    }

    function applyPreset() {
      if (searchPreset.value === 'custom') return
      const preset = presetValues[searchPreset.value]
      if (!preset) return
      mode.value = preset.mode
      sourceProfile.value = preset.sourceProfile
      disableDeepProcess.value = preset.disableDeepProcess
      preferredDomainsText.value = preset.preferredDomainsText
      blockedDomainsText.value = preset.blockedDomainsText
      domainPreferenceMode.value = preset.domainPreferenceMode
    }

    function buildStrategyPayload() {
      return {
        maxResults: maxResults.value,
        skipLocal: skipLocal.value,
        disableDeepProcess: disableDeepProcess.value,
        mode: mode.value,
        sourceProfile: sourceProfile.value,
        preferredDomainsText: preferredDomainsText.value,
        blockedDomainsText: blockedDomainsText.value,
        domainPreferenceMode: domainPreferenceMode.value,
        customStrategyName: customStrategyName.value || '我的来源策略',
        selectedEngines: [...selectedEngines.value],
      }
    }

    function applyStrategyPayload(payload) {
      if (!payload) return
      maxResults.value = Number(payload.maxResults || 5)
      skipLocal.value = !!payload.skipLocal
      disableDeepProcess.value = !!payload.disableDeepProcess
      mode.value = payload.mode || 'balanced'
      sourceProfile.value = payload.sourceProfile || 'general'
      preferredDomainsText.value = payload.preferredDomainsText || ''
      blockedDomainsText.value = payload.blockedDomainsText || ''
      domainPreferenceMode.value = payload.domainPreferenceMode || 'prefer'
      customStrategyName.value = payload.customStrategyName || '我的来源策略'
      selectedEngines.value = Array.isArray(payload.selectedEngines) ? payload.selectedEngines : []
    }

    function saveCustomStrategy() {
      const payload = buildStrategyPayload()
      localStorage.setItem(customStrategyKey, JSON.stringify(payload))
      hasSavedStrategy.value = true
      savedStrategyName.value = payload.customStrategyName
      searchPreset.value = 'custom'
    }

    function loadSavedStrategy() {
      const raw = localStorage.getItem(customStrategyKey)
      if (!raw) return
      try {
        applyStrategyPayload(JSON.parse(raw))
        searchPreset.value = 'custom'
        hasSavedStrategy.value = true
        savedStrategyName.value = JSON.parse(raw).customStrategyName || '我的来源策略'
      } catch (e) {
        console.warn('Failed to load saved search strategy', e)
      }
    }

    onMounted(() => {
      const raw = localStorage.getItem(customStrategyKey)
      hasSavedStrategy.value = !!raw
      if (raw) {
        try {
          savedStrategyName.value = JSON.parse(raw).customStrategyName || '我的来源策略'
        } catch (e) {
          console.warn('Failed to parse saved search strategy', e)
        }
      }
    })

    async function doSearch() {
      if (!query.value.trim()) return
      loading.value = true
      error.value = ''
      result.value = null
      try {
        const body = {
          query: query.value,
          max_results: maxResults.value,
          use_cache: true,
          skip_local: skipLocal.value,
          disable_deep_process: disableDeepProcess.value,
          mode: mode.value,
          source_profile: sourceProfile.value,
        }
        const preferredDomains = preferredDomainsText.value.split(',').map(v => v.trim()).filter(Boolean)
        const blockedDomains = blockedDomainsText.value.split(',').map(v => v.trim()).filter(Boolean)
        if (preferredDomains.length > 0) body.preferred_domains = preferredDomains
        if (blockedDomains.length > 0) body.blocked_domains = blockedDomains
        if (preferredDomains.length > 0 || blockedDomains.length > 0) {
          body.domain_preference_mode = domainPreferenceMode.value
        }
        if (selectedEngines.value.length > 0) {
          body.engines = selectedEngines.value.join(',')
        }
        result.value = await api('/api/v1/search', { method: 'POST', body })
      } catch (e) {
        error.value = e.message
      } finally {
        loading.value = false
      }
    }

    function truncate(s, n) {
      if (!s) return ''
      return s.length > n ? s.slice(0, n) + '…' : s
    }

    return {
      query,
      maxResults,
      skipLocal,
      disableDeepProcess,
      searchPreset,
      applyPreset,
      mode,
      sourceProfile,
      preferredDomainsText,
      blockedDomainsText,
      domainPreferenceMode,
      customStrategyName,
      presetDescriptions,
      saveCustomStrategy,
      loadSavedStrategy,
      hasSavedStrategy,
      savedStrategyName,
      loading,
      error,
      result,
      doSearch,
      truncate,
      engineOptions,
      selectedEngines,
    }
  },
}

// ── 配置页 ──
const ConfigPage = {
  template: `
    <div>
      <div v-if="msg" :class="'msg ' + msgType">{{ msg }}</div>
      <div v-if="loading" class="loading">加载中…</div>
      <div v-else-if="config">
        <div class="form-section" v-for="(section, key) in config" :key="key">
          <h4>{{ sectionNames[key] || key }}</h4>
          <div class="form-row">
            <div class="form-group" v-for="(val, field) in section" :key="field">
              <label>{{ fieldLabels[key] && fieldLabels[key][field] || field }}</label>

              <!-- 嵌入模型特殊控件 -->
              <template v-if="key === 'chroma' && field === 'embedding_model'">
                <select v-model="modelPreset" @change="onPresetChange" style="margin-bottom:6px">
                  <option v-for="m in modelPresets" :key="m.value" :value="m.value">{{ m.label }}</option>
                </select>
                <input v-if="modelPreset === '__custom__'"
                       type="text" v-model="config[key][field]"
                       placeholder="输入本地模型路径或 HuggingFace 模型名" />
                <div v-else style="font-size:12px;color:#666;margin-top:2px">{{ config[key][field] }}</div>
              </template>

              <!-- 摘要后端特殊控件 -->
              <template v-else-if="key === 'deep_process' && field === 'summary_backend'">
                <select v-model="config[key][field]">
                  <option value="extractive">extractive（抽取式，无需 LLM）</option>
                  <option value="lmstudio">lmstudio（本地 OpenAI 兼容接口）</option>
                </select>
              </template>

              <!-- 摘要模型特殊控件 -->
              <template v-else-if="key === 'deep_process' && field === 'summary_model'">
                <select v-model="summaryModelPreset" @change="onSummaryPresetChange" style="margin-bottom:6px">
                  <option v-for="m in summaryModelPresets" :key="m.value" :value="m.value">{{ m.label }}</option>
                </select>
                <input v-if="summaryModelPreset === '__custom__'"
                       type="text" v-model="config[key][field]"
                       placeholder="输入 LM Studio / OpenAI 兼容模型名" />
                <div v-else style="font-size:12px;color:#666;margin-top:2px">{{ config[key][field] }}</div>
              </template>

              <template v-else-if="typeof val === 'boolean'">
                <label class="toggle">
                  <input type="checkbox" v-model="config[key][field]" />
                  <span class="slider"></span>
                </label>
              </template>
              <template v-else-if="typeof val === 'number'">
                <input type="number" v-model.number="config[key][field]" step="any" />
              </template>
              <template v-else>
                <input type="text" v-model="config[key][field]" />
              </template>
            </div>
          </div>
        </div>
        <button class="btn btn-primary" @click="saveConfig" :disabled="saving">{{ saving ? '保存中…' : '保存配置' }}</button>
      </div>
    </div>
  `,
  setup() {
    const config = ref(null)
    const loading = ref(true)
    const saving = ref(false)
    const msg = ref('')
    const msgType = ref('msg-success')

    const sectionNames = {
      searxng: 'SearXNG 搜索引擎',
      lightpanda: 'LightPanda 渲染',
      chroma: 'ChromaDB 向量库',
      process: '文本处理',
      deep_process: '深度处理',
      cache: '缓存',
    }

    const fieldLabels = {
      chroma: {
        embedding_model: '嵌入模型',
        embedding_model_path: '嵌入模型路径',
      },
      deep_process: {
        summary_backend: '摘要后端',
        summary_api_url: '摘要 API 地址',
        summary_model: '摘要模型',
        summary_model_path: '摘要模型路径',
      },
    }

    // 预设模型列表
    const modelPresets = [
      { value: 'sentence-transformers/all-MiniLM-L6-v2',                   label: 'all-MiniLM-L6-v2（英文，快速）' },
      { value: 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2', label: 'paraphrase-multilingual-MiniLM-L12-v2（多语言）' },
      { value: 'sentence-transformers/all-mpnet-base-v2',                   label: 'all-mpnet-base-v2（英文，高质量）' },
      { value: 'BAAI/bge-small-zh-v1.5',                                    label: 'bge-small-zh（中文，轻量）' },
      { value: 'BAAI/bge-base-zh-v1.5',                                     label: 'bge-base-zh（中文，均衡）' },
      { value: '__custom__',                                                 label: '自定义路径…' },
    ]
    const modelPreset = ref('sentence-transformers/all-MiniLM-L6-v2')
    const summaryModelPresets = [
      { value: 'google/gemma-3-1b', label: 'google/gemma-3-1b（本地轻量摘要）' },
      { value: 'qwen3.5-35b-a3b-uncensored-hauhaucs-aggressive-mlx-mxfp8', label: 'qwen3.5-35b（本地大模型，较慢）' },
      { value: '__custom__', label: '自定义模型名…' },
    ]
    const summaryModelPreset = ref('google/gemma-3-1b')

    onMounted(async () => {
      try {
        config.value = await api('/api/v1/config/')
        // 加载完成后同步 modelPreset 下拉状态
        const currentModel = config.value?.chroma?.embedding_model
        if (currentModel) {
          const match = modelPresets.find(m => m.value === currentModel)
          modelPreset.value = match ? currentModel : '__custom__'
        }
        const currentSummaryModel = config.value?.deep_process?.summary_model
        if (currentSummaryModel) {
          const match = summaryModelPresets.find(m => m.value === currentSummaryModel)
          summaryModelPreset.value = match ? currentSummaryModel : '__custom__'
        }
      } catch (e) {
        msg.value = '加载配置失败: ' + e.message
        msgType.value = 'msg-error'
      } finally {
        loading.value = false
      }
    })

    function onPresetChange() {
      if (modelPreset.value !== '__custom__') {
        config.value.chroma.embedding_model = modelPreset.value
      }
    }

    function onSummaryPresetChange() {
      if (summaryModelPreset.value !== '__custom__') {
        config.value.deep_process.summary_model = summaryModelPreset.value
      }
    }

    async function saveConfig() {
      saving.value = true
      msg.value = ''
      try {
        for (const [section, sectionData] of Object.entries(config.value)) {
          await api('/api/v1/config/', {
            method: 'PUT',
            body: { section, data: sectionData },
          })
        }
        msg.value = '配置已保存，重启服务后生效'
        msgType.value = 'msg-success'
      } catch (e) {
        msg.value = '保存失败: ' + e.message
        msgType.value = 'msg-error'
      } finally {
        saving.value = false
      }
    }

    return { config, loading, saving, msg, msgType, sectionNames, fieldLabels,
             modelPresets, modelPreset, onPresetChange,
             summaryModelPresets, summaryModelPreset, onSummaryPresetChange,
             saveConfig }
  },
}

// ── 算法配置页 ──
const AlgorithmsPage = {
  template: `
    <div>
      <div v-if="msg" :class="'msg ' + msgType">{{ msg }}</div>
      <div v-if="loading" class="loading">加载中…</div>
      <div v-else-if="params">
        <div class="form-section" v-for="(section, key) in params" :key="key">
          <h4>{{ sectionNames[key] || key }}</h4>
          <div class="form-row">
            <div class="form-group" v-for="(val, field) in section" :key="field">
              <label>{{ field }}</label>
              <template v-if="typeof val === 'boolean'">
                <label class="toggle">
                  <input type="checkbox" v-model="params[key][field]" />
                  <span class="slider"></span>
                </label>
              </template>
              <template v-else-if="typeof val === 'number'">
                <input type="number" v-model.number="params[key][field]" step="any" />
              </template>
              <template v-else>
                <input type="text" v-model="params[key][field]" />
              </template>
            </div>
          </div>
        </div>
        <div style="display:flex;gap:8px">
          <button class="btn btn-primary" @click="save" :disabled="saving">{{ saving ? '保存中…' : '保存' }}</button>
          <button class="btn btn-outline" @click="reset">恢复默认</button>
        </div>
      </div>
    </div>
  `,
  setup() {
    const params = ref(null)
    const loading = ref(true)
    const saving = ref(false)
    const msg = ref('')
    const msgType = ref('msg-success')

    const sectionNames = { process: '文本处理参数', deep_process: '深度处理参数', chroma: '向量检索参数' }

    onMounted(async () => {
      try { params.value = await api('/api/v1/algorithms/') }
      catch (e) { msg.value = '加载失败: ' + e.message; msgType.value = 'msg-error' }
      finally { loading.value = false }
    })

    async function save() {
      saving.value = true; msg.value = ''
      try {
        await api('/api/v1/algorithms/', { method: 'PUT', body: params.value })
        msg.value = '算法参数已保存'; msgType.value = 'msg-success'
      } catch (e) { msg.value = '保存失败: ' + e.message; msgType.value = 'msg-error' }
      finally { saving.value = false }
    }

    async function reset() {
      try {
        await api('/api/v1/algorithms/reset', { method: 'POST' })
        params.value = await api('/api/v1/algorithms/')
        msg.value = '已恢复默认值'; msgType.value = 'msg-success'
      } catch (e) { msg.value = '重置失败: ' + e.message; msgType.value = 'msg-error' }
    }

    return { params, loading, saving, msg, msgType, sectionNames, save, reset }
  },
}

// ── 缓存页 ──
const CachePage = {
  template: `
    <div>
      <div v-if="msg" :class="'msg ' + msgType">{{ msg }}</div>
      <div v-if="loading" class="loading">加载中…</div>
      <template v-else>
        <div class="stats-row">
          <div class="stat-card">
            <div class="stat-value">{{ stats.total || 0 }}</div>
            <div class="stat-label">缓存条目</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{{ stats.hits || 0 }}</div>
            <div class="stat-label">命中次数</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{{ stats.misses || 0 }}</div>
            <div class="stat-label">未命中次数</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{{ (stats.hit_rate || 0).toFixed(1) }}%</div>
            <div class="stat-label">命中率</div>
          </div>
        </div>
        <button class="btn btn-danger" @click="clearCache" :disabled="clearing">{{ clearing ? '清空中…' : '清空缓存' }}</button>
      </template>
    </div>
  `,
  setup() {
    const stats = ref({})
    const loading = ref(true)
    const clearing = ref(false)
    const msg = ref('')
    const msgType = ref('msg-success')

    onMounted(async () => {
      try { stats.value = await api('/api/v1/cache/stats') }
      catch (e) { msg.value = '加载失败: ' + e.message; msgType.value = 'msg-error' }
      finally { loading.value = false }
    })

    async function clearCache() {
      if (!confirm('确定要清空缓存吗？')) return
      clearing.value = true; msg.value = ''
      try {
        await api('/api/v1/cache/', { method: 'DELETE' })
        stats.value = await api('/api/v1/cache/stats')
        msg.value = '缓存已清空'; msgType.value = 'msg-success'
      } catch (e) { msg.value = '清空失败: ' + e.message; msgType.value = 'msg-error' }
      finally { clearing.value = false }
    }

    return { stats, loading, clearing, msg, msgType, clearCache }
  },
}

// ── 向量库页 ──
const VectorPage = {
  template: `
    <div>
      <div v-if="msg" :class="'msg ' + msgType">{{ msg }}</div>
      <div v-if="loading" class="loading">加载中…</div>
      <template v-else>
        <div class="stats-row">
          <div class="stat-card">
            <div class="stat-value">{{ stats.count || 0 }}</div>
            <div class="stat-label">文档数量</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{{ stats.name || '-' }}</div>
            <div class="stat-label">集合名称</div>
          </div>
        </div>

        <div class="card" style="margin-bottom:16px">
          <h3>手动录入</h3>
          <div class="form-row">
            <div class="form-group">
              <label>来源 URL</label>
              <input type="text" v-model="manualForm.url" placeholder="manual://entry 或真实来源地址" />
            </div>
            <div class="form-group">
              <label>Chunk ID</label>
              <input type="number" v-model.number="manualForm.chunk_id" min="0" />
            </div>
            <div class="form-group">
              <label style="display:flex;align-items:center;gap:8px">
                <label class="toggle">
                  <input type="checkbox" v-model="manualForm.auto_chunk" />
                  <span class="slider"></span>
                </label>
                自动分块入库
              </label>
            </div>
          </div>
          <div class="form-group" style="margin-bottom:12px">
            <label>元数据（JSON，可选）</label>
            <textarea v-model="manualForm.metadataText" rows="4" placeholder='{"category":"manual","tags":["demo"]}'></textarea>
          </div>
          <div class="form-group" style="margin-bottom:12px">
            <label>正文</label>
            <textarea v-model="manualForm.text" rows="8" placeholder="输入要写入向量库的文本"></textarea>
          </div>
          <div style="display:flex;gap:8px;flex-wrap:wrap">
            <button class="btn btn-primary" @click="submitManualEntry" :disabled="submitting || !manualForm.text.trim()">
              {{ submitting ? '写入中…' : '写入向量库' }}
            </button>
            <button class="btn btn-outline" @click="resetManualForm">清空表单</button>
            <button class="btn btn-danger" @click="clearAllDocuments" :disabled="clearing">
              {{ clearing ? '清空中…' : '清空数据库' }}
            </button>
          </div>
        </div>

        <div class="card">
          <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:12px">
            <h3 style="margin:0">文档列表</h3>
            <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
              <input type="text" v-model="searchQuery" placeholder="搜索 ID / 内容 / 元数据" @keyup.enter="applySearch" style="min-width:240px" />
              <button class="btn btn-outline" @click="applySearch">搜索</button>
              <button class="btn btn-outline" @click="resetSearch">重置</button>
            </div>
          </div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th style="width:50px">#</th>
                  <th style="width:180px">文档 ID</th>
                  <th style="width:300px">来源 URL</th>
                  <th>内容预览</th>
                  <th style="width:80px">Chunk</th>
                  <th style="width:140px">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(doc, i) in docs" :key="doc.id">
                  <td>{{ (page - 1) * pageSize + i + 1 }}</td>
                  <td style="word-break:break-all;font-size:12px">{{ doc.id }}</td>
                  <td style="word-break:break-all;font-size:12px">{{ doc.url || (doc.metadata && doc.metadata.source_url) || '-' }}</td>
                  <td><div style="max-height:60px;overflow:hidden;font-size:12px">{{ previewText(doc.text) }}</div></td>
                  <td>{{ doc.metadata && doc.metadata.chunk_id }}</td>
                  <td>
                    <div style="display:flex;gap:6px;flex-wrap:wrap">
                      <button class="btn btn-outline" @click="startEdit(doc)">编辑</button>
                      <button class="btn btn-danger" @click="deleteDocument(doc.id)">删除</button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-if="!docs.length" class="empty">暂无文档</div>
          <div class="pagination">
            <button :disabled="page <= 1" @click="page--; loadDocs()">上一页</button>
            <span class="page-info">第 {{ page }} 页 / 共 {{ totalPages }} 页 ({{ total }} 条)</span>
            <button :disabled="page >= totalPages" @click="page++; loadDocs()">下一页</button>
          </div>
        </div>

        <div class="card" v-if="editForm.id" style="margin-top:16px">
          <h3>编辑文档</h3>
          <div class="form-row">
            <div class="form-group">
              <label>文档 ID</label>
              <input type="text" :value="editForm.id" disabled />
            </div>
            <div class="form-group">
              <label>来源 URL</label>
              <input type="text" v-model="editForm.url" />
            </div>
            <div class="form-group">
              <label>Chunk ID</label>
              <input type="number" v-model.number="editForm.chunk_id" min="0" />
            </div>
          </div>
          <div class="form-group" style="margin-bottom:12px">
            <label>元数据（JSON）</label>
            <textarea v-model="editForm.metadataText" rows="4"></textarea>
          </div>
          <div class="form-group" style="margin-bottom:12px">
            <label>正文</label>
            <textarea v-model="editForm.text" rows="8"></textarea>
          </div>
          <div style="display:flex;gap:8px;flex-wrap:wrap">
            <button class="btn btn-primary" @click="saveEdit" :disabled="savingEdit || !editForm.text.trim()">
              {{ savingEdit ? '保存中…' : '保存修改' }}
            </button>
            <button class="btn btn-outline" @click="cancelEdit">取消</button>
          </div>
        </div>
      </template>
    </div>
  `,
  setup() {
    const stats = ref({})
    const docs = ref([])
    const total = ref(0)
    const page = ref(1)
    const pageSize = 20
    const loading = ref(true)
    const msg = ref('')
    const msgType = ref('msg-success')
    const searchQuery = ref('')
    const appliedQuery = ref('')
    const submitting = ref(false)
    const clearing = ref(false)
    const savingEdit = ref(false)
    const manualForm = reactive({
      url: 'manual://entry',
      chunk_id: 0,
      auto_chunk: true,
      metadataText: '{"source":"manual"}',
      text: '',
    })
    const editForm = reactive({
      id: '',
      url: '',
      chunk_id: 0,
      metadataText: '{}',
      text: '',
    })

    const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))

    function showMessage(text, isError = false) {
      msg.value = text
      msgType.value = isError ? 'msg-error' : 'msg-success'
    }

    function parseMetadata(text) {
      const raw = (text || '').trim()
      if (!raw) return {}
      return JSON.parse(raw)
    }

    function previewText(text) {
      if (!text) return ''
      return text.length > 150 ? text.slice(0, 150) + '…' : text
    }

    async function loadDocs() {
      try {
        const suffix = appliedQuery.value ? `&query=${encodeURIComponent(appliedQuery.value)}` : ''
        const data = await api(`/api/v1/vector/documents?page=${page.value}&size=${pageSize}${suffix}`)
        docs.value = data.documents || []
        total.value = data.total || 0
      } catch (e) {
        showMessage('加载文档失败: ' + e.message, true)
      }
    }

    async function refreshAll() {
      stats.value = await api('/api/v1/vector/stats')
      await loadDocs()
    }

    function applySearch() {
      page.value = 1
      appliedQuery.value = searchQuery.value.trim()
      loadDocs()
    }

    function resetSearch() {
      searchQuery.value = ''
      appliedQuery.value = ''
      page.value = 1
      loadDocs()
    }

    function resetManualForm() {
      manualForm.url = 'manual://entry'
      manualForm.chunk_id = 0
      manualForm.auto_chunk = true
      manualForm.metadataText = '{"source":"manual"}'
      manualForm.text = ''
    }

    async function submitManualEntry() {
      submitting.value = true
      try {
        await api('/api/v1/vector/documents/manual', {
          method: 'POST',
          body: {
            url: manualForm.url,
            chunk_id: manualForm.chunk_id,
            auto_chunk: manualForm.auto_chunk,
            metadata: parseMetadata(manualForm.metadataText),
            text: manualForm.text,
          },
        })
        showMessage('手动录入成功')
        resetManualForm()
        await refreshAll()
      } catch (e) {
        showMessage('手动录入失败: ' + e.message, true)
      } finally {
        submitting.value = false
      }
    }

    async function clearAllDocuments() {
      if (!confirm('确定清空整个向量库吗？此操作不可撤销。')) return
      clearing.value = true
      try {
        await api('/api/v1/vector/collection', { method: 'DELETE' })
        cancelEdit()
        showMessage('向量库已清空')
        await refreshAll()
      } catch (e) {
        showMessage('清空失败: ' + e.message, true)
      } finally {
        clearing.value = false
      }
    }

    function startEdit(doc) {
      editForm.id = doc.id
      editForm.url = doc.url || (doc.metadata && doc.metadata.source_url) || ''
      editForm.chunk_id = Number((doc.metadata && doc.metadata.chunk_id) || 0)
      editForm.text = doc.text || ''
      editForm.metadataText = JSON.stringify(doc.metadata || {}, null, 2)
    }

    function cancelEdit() {
      editForm.id = ''
      editForm.url = ''
      editForm.chunk_id = 0
      editForm.metadataText = '{}'
      editForm.text = ''
    }

    async function saveEdit() {
      savingEdit.value = true
      try {
        await api(`/api/v1/vector/documents/${encodeURIComponent(editForm.id)}`, {
          method: 'PUT',
          body: {
            url: editForm.url,
            chunk_id: editForm.chunk_id,
            metadata: parseMetadata(editForm.metadataText),
            text: editForm.text,
          },
        })
        showMessage('文档已更新')
        await refreshAll()
      } catch (e) {
        showMessage('更新失败: ' + e.message, true)
      } finally {
        savingEdit.value = false
      }
    }

    async function deleteDocument(id) {
      if (!confirm('确定删除这条文档吗？')) return
      try {
        await api('/api/v1/vector/documents', {
          method: 'DELETE',
          body: [id],
        })
        if (editForm.id === id) cancelEdit()
        showMessage('文档已删除')
        await refreshAll()
      } catch (e) {
        showMessage('删除失败: ' + e.message, true)
      }
    }

    onMounted(async () => {
      try {
        await refreshAll()
      } catch (e) {
        showMessage('加载失败: ' + e.message, true)
      } finally {
        loading.value = false
      }
    })

    return {
      stats,
      docs,
      total,
      page,
      pageSize,
      totalPages,
      loading,
      msg,
      msgType,
      searchQuery,
      manualForm,
      editForm,
      submitting,
      clearing,
      savingEdit,
      loadDocs,
      applySearch,
      resetSearch,
      previewText,
      submitManualEntry,
      resetManualForm,
      clearAllDocuments,
      startEdit,
      cancelEdit,
      saveEdit,
      deleteDocument,
    }
  },
}

// ── Token 管理页 ──
const TokensPage = {
  template: `
    <div>
      <div v-if="msg" :class="'msg ' + msgType">{{ msg }}</div>

      <div class="card" style="margin-bottom:16px">
        <h3>创建 Token</h3>
        <div class="form-row">
          <div class="form-group">
            <label>名称</label>
            <input v-model="form.name" placeholder="例如：mcp-bot-01" />
          </div>
          <div class="form-group">
            <label>角色</label>
            <select v-model="form.role">
              <option value="default">default</option>
              <option value="admin">admin</option>
            </select>
          </div>
          <div class="form-group">
            <label>备注</label>
            <input v-model="form.notes" placeholder="可选备注" />
          </div>
        </div>
        <button class="btn btn-primary" @click="createToken" :disabled="creating || !form.name.trim()">
          {{ creating ? '生成中…' : '生成 Token' }}
        </button>
        <div v-if="createdToken" class="card" style="margin-top:12px;background:#f6fbff;border-color:#b6d4fe">
          <div style="font-size:13px;color:#555;margin-bottom:6px">请立即保存，离开后不会再次展示完整 Token：</div>
          <div style="font-family:monospace;word-break:break-all">{{ createdToken.api_key }}</div>
        </div>
      </div>

      <div class="card">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
          <h3 style="margin:0">Token 列表</h3>
          <button class="btn btn-outline" @click="loadTokens">刷新</button>
        </div>
        <div v-if="loading" class="loading">加载中…</div>
        <template v-else>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>名称</th>
                  <th>角色</th>
                  <th>状态</th>
                  <th>搜索调用</th>
                  <th>API 调用</th>
                  <th>最后使用</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="token in tokens" :key="token.id">
                  <td>{{ token.name }}</td>
                  <td>{{ token.role }}</td>
                  <td>{{ token.status }}</td>
                  <td>{{ token.search_calls || 0 }}</td>
                  <td>{{ token.api_calls || 0 }}</td>
                  <td>{{ token.last_used_at || '-' }}</td>
                  <td>
                    <div style="display:flex;gap:8px;flex-wrap:wrap">
                      <button class="btn btn-outline" @click="viewUsage(token)">查看调用</button>
                      <button class="btn btn-danger" @click="revokeToken(token)" :disabled="token.status !== 'active'">停用</button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-if="!tokens.length" class="empty">暂无 Token</div>
        </template>
      </div>

      <div v-if="usage" class="card" style="margin-top:16px">
        <h3>调用详情：{{ usage.token_name }}</h3>
        <div class="stats-row" style="margin-bottom:12px">
          <div class="stat-card">
            <div class="stat-value">{{ usage.search_logs?.length || 0 }}</div>
            <div class="stat-label">最近搜索记录</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{{ usage.api_logs?.length || 0 }}</div>
            <div class="stat-label">最近 API 记录</div>
          </div>
        </div>
        <div class="form-section">
          <h4>搜索调用</h4>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>时间</th>
                  <th>查询</th>
                  <th>来源</th>
                  <th>耗时</th>
                  <th>客户端</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(log, idx) in usage.search_logs" :key="'s-' + idx">
                  <td>{{ log.timestamp }}</td>
                  <td>{{ log.query }}</td>
                  <td>{{ log.source }}</td>
                  <td>{{ log.total_time ? log.total_time.toFixed(3) + 's' : '-' }}</td>
                  <td>{{ log.client_type || '-' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
        <div class="form-section">
          <h4>API 调用</h4>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>时间</th>
                  <th>端点</th>
                  <th>方法</th>
                  <th>状态</th>
                  <th>耗时</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(log, idx) in usage.api_logs" :key="'a-' + idx">
                  <td>{{ log.timestamp }}</td>
                  <td>{{ log.endpoint }}</td>
                  <td>{{ log.method }}</td>
                  <td>{{ log.status_code }}</td>
                  <td>{{ log.response_time ? log.response_time.toFixed(3) + 's' : '-' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  `,
  setup() {
    const tokens = ref([])
    const usage = ref(null)
    const loading = ref(true)
    const creating = ref(false)
    const createdToken = ref(null)
    const msg = ref('')
    const msgType = ref('msg-success')
    const form = reactive({
      name: '',
      role: 'default',
      notes: '',
    })

    async function loadTokens() {
      loading.value = true
      try {
        const data = await api('/api/v1/tokens')
        tokens.value = data.tokens || []
      } catch (e) {
        msg.value = '加载 Token 失败: ' + e.message
        msgType.value = 'msg-error'
      } finally {
        loading.value = false
      }
    }

    async function createToken() {
      creating.value = true
      msg.value = ''
      try {
        createdToken.value = await api('/api/v1/tokens', { method: 'POST', body: { ...form } })
        form.name = ''
        form.role = 'default'
        form.notes = ''
        msg.value = 'Token 已生成'
        msgType.value = 'msg-success'
        await loadTokens()
      } catch (e) {
        msg.value = '创建失败: ' + e.message
        msgType.value = 'msg-error'
      } finally {
        creating.value = false
      }
    }

    async function revokeToken(token) {
      try {
        await api(`/api/v1/tokens/${token.id}/revoke`, { method: 'POST' })
        msg.value = `已停用 ${token.name}`
        msgType.value = 'msg-success'
        await loadTokens()
      } catch (e) {
        msg.value = '停用失败: ' + e.message
        msgType.value = 'msg-error'
      }
    }

    async function viewUsage(token) {
      try {
        usage.value = await api(`/api/v1/tokens/${token.id}/usage`)
      } catch (e) {
        msg.value = '加载调用详情失败: ' + e.message
        msgType.value = 'msg-error'
      }
    }

    onMounted(loadTokens)

    return { tokens, usage, loading, creating, createdToken, msg, msgType, form, loadTokens, createToken, revokeToken, viewUsage }
  },
}

// ── 日志页 ──
const LogsPage = {
  template: `
    <div>
      <div v-if="msg" :class="'msg ' + msgType">{{ msg }}</div>

      <div class="stats-row" v-if="logStats">
        <div class="stat-card">
          <div class="stat-value">{{ logStats.total_search_logs || 0 }}</div>
          <div class="stat-label">搜索日志总数</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ logStats.total_api_logs || 0 }}</div>
          <div class="stat-label">API 日志总数</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ (logStats.avg_search_time || 0).toFixed(2) }}s</div>
          <div class="stat-label">平均搜索时间</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ logStats.last_24h_searches || 0 }}</div>
          <div class="stat-label">24h 搜索次数</div>
        </div>
      </div>

      <div class="card">
        <h3>搜索日志</h3>
        <div v-if="loading" class="loading">加载中…</div>
        <template v-else>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>时间</th>
                  <th>查询</th>
                  <th>来源</th>
                  <th>结果数</th>
                  <th>耗时</th>
                  <th>客户端</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="log in logs" :key="log.id">
                  <td style="white-space:nowrap">{{ log.timestamp }}</td>
                  <td>{{ log.query }}</td>
                  <td><span :class="log.source==='local'?'badge badge-local':'badge badge-online'">{{ log.source }}</span></td>
                  <td>{{ log.results_count }}</td>
                  <td>{{ log.total_time ? log.total_time.toFixed(3) + 's' : '-' }}</td>
                  <td>{{ log.client_type || '-' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-if="!logs.length" class="empty">暂无日志</div>
          <div class="pagination">
            <button :disabled="page <= 1" @click="page--; loadLogs()">上一页</button>
            <span class="page-info">第 {{ page }} 页 / 共 {{ totalPages }} 页 ({{ total }} 条)</span>
            <button :disabled="page >= totalPages" @click="page++; loadLogs()">下一页</button>
          </div>
        </template>
      </div>
    </div>
  `,
  setup() {
    const logs = ref([])
    const logStats = ref(null)
    const total = ref(0)
    const page = ref(1)
    const pageSize = 20
    const loading = ref(true)
    const msg = ref('')
    const msgType = ref('msg-success')

    const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))

    async function loadLogs() {
      try {
        const data = await api(`/api/v1/logs/search?page=${page.value}&size=${pageSize}`)
        logs.value = data.logs || []
        total.value = data.total || 0
      } catch (e) {
        msg.value = '加载日志失败: ' + e.message
        msgType.value = 'msg-error'
      }
    }

    onMounted(async () => {
      try {
        logStats.value = await api('/api/v1/logs/stats')
        await loadLogs()
      } catch (e) {
        msg.value = '加载失败: ' + e.message
        msgType.value = 'msg-error'
      } finally {
        loading.value = false
      }
    })

    return { logs, logStats, total, page, pageSize, totalPages, loading, msg, msgType, loadLogs }
  },
}

// ── 主 App ──
const app = createApp({
  components: { SearchPage, ConfigPage, AlgorithmsPage, CachePage, VectorPage, TokensPage, LogsPage },
  setup() {
    const currentPage = ref('search')

    const pages = [
      { id: 'search',     label: '搜索',     icon: '🔍' },
      { id: 'config',     label: '配置',     icon: '⚙️' },
      { id: 'algorithms', label: '算法配置', icon: '🧮' },
      { id: 'cache',      label: '缓存',     icon: '📦' },
      { id: 'vector',     label: '向量库',   icon: '🗄️' },
      { id: 'tokens',     label: 'Token',    icon: '🔐' },
      { id: 'logs',       label: '日志',     icon: '📋' },
    ]

    const pageTitle = computed(() => {
      const p = pages.find(p => p.id === currentPage.value)
      return p ? p.label : ''
    })

    return { currentPage, pages, pageTitle, apiKey }
  },
})

app.mount('#app')
