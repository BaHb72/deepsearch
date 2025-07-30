<template>
  <div
      :class="['status-card', `status-${type}`, { 'is-clickable': clickable }]"
      @click="handleClick"
  >
    <!-- 背景装饰 -->
    <div class="card-bg-decoration">
      <div class="decoration-circle decoration-circle-1"></div>
      <div class="decoration-circle decoration-circle-2"></div>
    </div>

    <!-- 卡片内容 -->
    <div class="card-content">
      <!-- 图标区域 -->
      <div class="icon-wrapper">
        <el-icon :size="iconSize" class="status-icon">
          <component :is="icon"/>
        </el-icon>
        <div v-if="pulse" class="pulse-ring"></div>
      </div>

      <!-- 文字内容 -->
      <div class="content-wrapper">
        <h3 class="title">{{ title }}</h3>
        <p v-if="subtitle" class="subtitle">{{ subtitle }}</p>

        <!-- 数值显示 -->
        <div v-if="value !== undefined" class="value-display">
          <span class="value">{{ formattedValue }}</span>
          <span v-if="unit" class="unit">{{ unit }}</span>
        </div>

        <!-- 状态标签 -->
        <el-tag
            v-if="status"
            :type="statusType"
            class="status-tag"
            effect="dark"
        >
          <span v-if="statusDot" class="status-dot"></span>
          {{ status }}
        </el-tag>

        <!-- 额外信息 -->
        <div v-if="$slots.extra" class="extra-content">
          <slot name="extra"></slot>
        </div>
      </div>

      <!-- 操作按钮 -->
      <div v-if="$slots.actions || action" class="action-wrapper">
        <slot name="actions">
          <el-button
              v-if="action"
              :size="actionSize"
              :type="actionType"
              @click.stop="handleAction"
          >
            {{ actionText }}
          </el-button>
        </slot>
      </div>
    </div>

    <!-- 进度条 -->
    <div v-if="progress !== undefined" class="progress-wrapper">
      <el-progress
          :percentage="progress"
          :show-text="false"
          :status="progressStatus"
          :stroke-width="6"
      />
    </div>
  </div>
</template>

<script setup>
import {computed} from 'vue'

// 定义组件名称
defineOptions({
  name: 'StatusCard'
})

// 定义 props
const props = defineProps({
  // 卡片类型
  type: {
    type: String,
    default: 'primary',
    validator: (value) => ['primary', 'success', 'warning', 'danger', 'info'].includes(value)
  },
  // 图标
  icon: {
    type: Object,
    required: true
  },
  // 图标大小
  iconSize: {
    type: Number,
    default: 48
  },
  // 标题
  title: {
    type: String,
    required: true
  },
  // 副标题
  subtitle: {
    type: String
  },
  // 数值
  value: {
    type: [Number, String]
  },
  // 单位
  unit: {
    type: String
  },
  // 状态文字
  status: {
    type: String
  },
  // 状态类型
  statusType: {
    type: String,
    default: ''
  },
  // 状态点
  statusDot: {
    type: Boolean,
    default: false
  },
  // 进度
  progress: {
    type: Number
  },
  // 进度状态
  progressStatus: {
    type: String
  },
  // 是否可点击
  clickable: {
    type: Boolean,
    default: false
  },
  // 是否显示脉冲动画
  pulse: {
    type: Boolean,
    default: false
  },
  // 操作按钮
  action: {
    type: Boolean,
    default: false
  },
  // 操作按钮文字
  actionText: {
    type: String,
    default: '查看详情'
  },
  // 操作按钮类型
  actionType: {
    type: String,
    default: 'primary'
  },
  // 操作按钮大小
  actionSize: {
    type: String,
    default: 'small'
  }
})

// 定义事件
const emit = defineEmits(['click', 'action'])

// 格式化数值
const formattedValue = computed(() => {
  if (typeof props.value === 'number') {
    // 如果是大数字，格式化显示
    if (props.value >= 1000000) {
      return (props.value / 1000000).toFixed(1) + 'M'
    } else if (props.value >= 1000) {
      return (props.value / 1000).toFixed(1) + 'K'
    }
    return props.value.toLocaleString()
  }
  return props.value
})

// 处理点击
const handleClick = () => {
  if (props.clickable) {
    emit('click')
  }
}

// 处理操作
const handleAction = () => {
  emit('action')
}
</script>

<style lang="scss" scoped>
@import '@/assets/styles/design-tokens.scss';

.status-card {
  position: relative;
  background: var(--card-bg);
  border-radius: $radius-xl;
  padding: $spacing-5;
  min-height: 160px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: all $duration-base $ease-out;
  border: 1px solid var(--border-lighter);

  &.is-clickable {
    cursor: pointer;

    &:hover {
      transform: translateY(-4px);
      box-shadow: $shadow-lg;

      .card-bg-decoration {
        .decoration-circle {
          transform: scale(1.1);
        }
      }

      .status-icon {
        transform: scale(1.1) rotate(5deg);
      }
    }
  }

  // 背景装饰
  .card-bg-decoration {
    position: absolute;
    top: 0;
    right: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
    opacity: 0.06;

    .decoration-circle {
      position: absolute;
      border-radius: 50%;
      transition: transform $duration-slow $ease-out;

      &-1 {
        width: 120px;
        height: 120px;
        top: -60px;
        right: -60px;
        background: currentColor;
      }

      &-2 {
        width: 80px;
        height: 80px;
        bottom: -40px;
        right: 40px;
        background: currentColor;
        opacity: 0.5;
      }
    }
  }

  // 卡片内容
  .card-content {
    position: relative;
    z-index: 1;
    display: flex;
    align-items: flex-start;
    gap: $spacing-4;
    flex: 1;
  }

  // 图标包装器
  .icon-wrapper {
    position: relative;
    flex-shrink: 0;

    .status-icon {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 56px;
      height: 56px;
      border-radius: $radius-lg;
      background: currentColor;
      color: white;
      transition: all $duration-base $ease-out;
      box-shadow: $shadow-md;
    }

    // 脉冲动画环
    .pulse-ring {
      position: absolute;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      width: 56px;
      height: 56px;
      border-radius: 50%;
      border: 2px solid currentColor;
      opacity: 0.3;
      animation: pulse 2s infinite;
    }
  }

  // 内容包装器
  .content-wrapper {
    flex: 1;
    min-width: 0;

    .title {
      margin: 0 0 $spacing-1 0;
      font-size: $font-size-base;
      font-weight: $font-weight-semibold;
      color: var(--text-primary);
      @include truncate;
    }

    .subtitle {
      margin: 0 0 $spacing-2 0;
      font-size: $font-size-xs;
      color: var(--text-secondary);
      @include truncate;
    }

    // 数值显示
    .value-display {
      margin-bottom: $spacing-3;
      min-height: 40px;
      display: flex;
      align-items: baseline;

      .value {
        font-size: $font-size-3xl;
        font-weight: $font-weight-bold;
        color: currentColor;
        letter-spacing: -0.02em;
        line-height: 1;
      }

      .unit {
        margin-left: $spacing-1;
        font-size: $font-size-lg;
        color: var(--text-secondary);
      }
    }

    // 状态标签
    .status-tag {
      border-radius: $radius-full;
      padding: $spacing-1 $spacing-3;
      font-weight: $font-weight-medium;

      .status-dot {
        display: inline-block;
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background: currentColor;
        margin-right: $spacing-1;
        @include breathing-animation;
      }
    }

    // 额外内容
    .extra-content {
      margin-top: $spacing-3;
      font-size: $font-size-sm;
      color: var(--text-secondary);
    }
  }

  // 操作包装器
  .action-wrapper {
    flex-shrink: 0;
    align-self: center;
  }

  // 进度条包装器
  .progress-wrapper {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 6px;
    background: var(--border-lighter);

    :deep(.el-progress) {
      line-height: 6px;

      .el-progress-bar__outer {
        height: 6px !important;
        background: transparent;
      }

      .el-progress-bar__inner {
        border-radius: 0;
      }
    }
  }

  // 没有进度条时的占位
  &:not(:has(.progress-wrapper)) {
    padding-bottom: calc(#{$spacing-5} + 6px);
  }

  // 不同类型的样式
  &.status-primary {
    color: $brand-primary;

    .card-bg-decoration {
      color: $brand-primary;
    }
  }

  &.status-success {
    color: $color-success;

    .card-bg-decoration {
      color: $color-success;
    }
  }

  &.status-warning {
    color: $color-warning;

    .card-bg-decoration {
      color: $color-warning;
    }
  }

  &.status-danger {
    color: $color-danger;

    .card-bg-decoration {
      color: $color-danger;
    }
  }

  &.status-info {
    color: $color-info;

    .card-bg-decoration {
      color: $color-info;
    }
  }
}

// 暗色主题
.dark {
  .status-card {
    background: var(--card-bg);
    border-color: var(--border-color);

    &.is-clickable:hover {
      border-color: var(--border-light);
    }
  }
}

// 响应式
@media (max-width: $breakpoint-md) {
  .status-card {
    padding: $spacing-4;

    .card-content {
      flex-direction: column;

      .icon-wrapper {
        margin-bottom: $spacing-3;
      }
    }
  }
}
</style>