<template>
  <div
      ref="cardRef"
      :class="['status-card', `status-${type}`, { 'is-clickable': clickable }]"
      @click="handleClick"
      @mouseleave="handleMouseLeave"
      @mousemove="handleMouseMove"
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
import {computed, ref} from 'vue'

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

// 3D倾斜效果的ref
const cardRef = ref(null)
const tiltX = ref(0)
const tiltY = ref(0)

// 格式化数值 - 增强版支持动画
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

// 处理鼠标移动 - 3D倾斜效果
const handleMouseMove = (event) => {
  if (!props.clickable || !cardRef.value) return

  const card = cardRef.value
  const rect = card.getBoundingClientRect()
  const x = event.clientX - rect.left
  const y = event.clientY - rect.top
  const centerX = rect.width / 2
  const centerY = rect.height / 2

  // 计算倾斜角度
  const angleX = (y - centerY) / centerY * -10 // -10度到10度
  const angleY = (x - centerX) / centerX * 10 // -10度到10度

  // 更新CSS变量
  card.style.setProperty('--tilt-x', `${angleX}deg`)
  card.style.setProperty('--tilt-y', `${angleY}deg`)
}

// 处理鼠标离开 - 重置倾斜
const handleMouseLeave = () => {
  if (!cardRef.value) return
  cardRef.value.style.setProperty('--tilt-x', '0deg')
  cardRef.value.style.setProperty('--tilt-y', '0deg')
}

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
@use '@/assets/styles/design-tokens.scss' as tokens;
@use '@/assets/styles/animations.scss' as animations;
@use '@/assets/styles/effects.scss' as effects;

.status-card {
  position: relative;
  background: var(--card-bg);
  border-radius: tokens.$radius-xl;
  padding: tokens.$spacing-5;
  min-height: 160px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: all tokens.$duration-base tokens.$ease-out;
  border: 1px solid var(--border-lighter);
  transform-style: preserve-3d;
  perspective: 1000px;

  // 玻璃态背景增强
  @include tokens.glassmorphism(0.95, 8px);

  // 添加微妙的渐变叠加
  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: linear-gradient(
            135deg,
            rgba(255, 255, 255, 0.1) 0%,
            transparent 50%
    );
    pointer-events: none;
    z-index: 1;
  }

  &.is-clickable {
    cursor: pointer;

    &:hover {
      transform: translateY(-4px) rotateX(var(--tilt-x, 0deg)) rotateY(var(--tilt-y, 0deg)) scale(1.02);
      box-shadow: tokens.$shadow-layered;

      // 增强发光效果
      &.status-primary {
        @include tokens.glow(tokens.$brand-primary, 20px, 0.4);
      }

      &.status-success {
        @include tokens.glow(tokens.$color-success, 20px, 0.4);
      }

      &.status-danger {
        @include tokens.glow(tokens.$color-danger, 20px, 0.4);
      }

      .card-bg-decoration {
        .decoration-circle {
          transform: scale(1.2);
          filter: blur(40px);
        }
      }

      .status-icon {
        transform: scale(1.15) rotate(10deg);
        filter: drop-shadow(0 8px 16px rgba(0, 0, 0, 0.2));
      }

      // 数值动画
      .value {
        transform: scale(1.05);
      }
    }

    &:active {
      transform: translateY(-2px) scale(0.98);
    }
  }

  // 背景装饰 - 增强版
  .card-bg-decoration {
    position: absolute;
    top: 0;
    right: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
    opacity: 0.08;

    .decoration-circle {
      position: absolute;
      border-radius: 50%;
      transition: all tokens.$duration-slow tokens.$ease-out;
      filter: blur(20px);
      animation: float 6s ease-in-out infinite;

      &-1 {
        width: 150px;
        height: 150px;
        top: -75px;
        right: -75px;
        background: radial-gradient(circle, currentColor 0%, transparent 70%);
        animation-delay: 0s;
      }

      &-2 {
        width: 100px;
        height: 100px;
        bottom: -50px;
        right: 30px;
        background: radial-gradient(circle, currentColor 0%, transparent 70%);
        opacity: 0.6;
        animation-delay: 3s;
      }
    }

    @keyframes float {
      0%, 100% {
        transform: translateY(0) scale(1);
      }
      50% {
        transform: translateY(-10px) scale(1.05);
      }
    }
  }

  // 卡片内容
  .card-content {
    position: relative;
    z-index: 1;
    display: flex;
    align-items: flex-start;
    gap: tokens.$spacing-4;
    flex: 1;
  }

  // 图标包装器 - 增强版
  .icon-wrapper {
    position: relative;
    flex-shrink: 0;
    z-index: 2;

    .status-icon {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 56px;
      height: 56px;
      border-radius: tokens.$radius-lg;
      background: currentColor;
      color: white;
      transition: all tokens.$duration-base tokens.$ease-out;
      box-shadow: tokens.$shadow-md,
      inset 0 1px 2px rgba(255, 255, 255, 0.2);
      position: relative;
      overflow: hidden;

      // 添加光泽效果
      &::before {
        content: '';
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: linear-gradient(
                45deg,
                transparent 30%,
                rgba(255, 255, 255, 0.2) 50%,
                transparent 70%
        );
        transform: rotate(45deg);
        transition: all 0.6s;
      }

      &:hover::before {
        animation: shimmer 0.6s;
      }
    }

    // 脉冲动画环 - 增强版
    .pulse-ring {
      position: absolute;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      width: 56px;
      height: 56px;
      border-radius: 50%;
      opacity: 0;

      &::before,
      &::after {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        border-radius: 50%;
        border: 2px solid currentColor;
        animation: pulseRing 2s ease-out infinite;
      }

      &::after {
        animation-delay: 1s;
      }
    }

    @keyframes pulseRing {
      0% {
        transform: scale(1);
        opacity: 0.8;
      }
      100% {
        transform: scale(1.5);
        opacity: 0;
      }
    }

    @keyframes shimmer {
      0% {
        transform: translateX(-100%) rotate(45deg);
      }
      100% {
        transform: translateX(100%) rotate(45deg);
      }
    }
  }

  // 内容包装器
  .content-wrapper {
    flex: 1;
    min-width: 0;

    .title {
      margin: 0 0 tokens.$spacing-1 0;
      font-size: tokens.$font-size-base;
      font-weight: tokens.$font-weight-semibold;
      color: var(--text-primary);
      @include tokens.truncate;
    }

    .subtitle {
      margin: 0 0 tokens.$spacing-2 0;
      font-size: tokens.$font-size-xs;
      color: var(--text-secondary);
      @include tokens.truncate;
    }

    // 数值显示 - 增强版带数字滚动
    .value-display {
      margin-bottom: tokens.$spacing-3;
      min-height: 40px;
      display: flex;
      align-items: baseline;
      position: relative;
      z-index: 2;

      .value {
        font-size: tokens.$font-size-3xl;
        font-weight: tokens.$font-weight-bold;
        color: currentColor;
        letter-spacing: -0.02em;
        line-height: 1;
        transition: all tokens.$duration-base tokens.$ease-out;
        text-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);

        // 数字变化时的动画
        animation: countUp 0.5s tokens.$ease-out;

        // 为金融数据添加特殊效果
        &.bullish {
          color: tokens.$color-bullish;
          animation: bullish 0.6s tokens.$ease-out;
        }

        &.bearish {
          color: tokens.$color-bearish;
          animation: bearish 0.6s tokens.$ease-out;
        }
      }

      .unit {
        margin-left: tokens.$spacing-1;
        font-size: tokens.$font-size-lg;
        color: var(--text-secondary);
        opacity: 0.7;
      }

      @keyframes countUp {
        from {
          transform: translateY(20px);
          opacity: 0;
        }
        to {
          transform: translateY(0);
          opacity: 1;
        }
      }
    }

    // 状态标签 - 增强版
    .status-tag {
      border-radius: tokens.$radius-full;
      padding: tokens.$spacing-1 tokens.$spacing-3;
      font-weight: tokens.$font-weight-medium;
      position: relative;
      overflow: hidden;

      // 添加微光效果
      &::before {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(
                90deg,
                transparent,
                rgba(255, 255, 255, 0.3),
                transparent
        );
        animation: tagShimmer 3s infinite;
      }

      .status-dot {
        display: inline-block;
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background: currentColor;
        margin-right: tokens.$spacing-1;
        @include tokens.breathing-animation;
        box-shadow: 0 0 8px currentColor;
      }

      @keyframes tagShimmer {
        0% {
          left: -100%;
        }
        100% {
          left: 100%;
        }
      }
    }

    // 额外内容
    .extra-content {
      margin-top: tokens.$spacing-3;
      font-size: tokens.$font-size-sm;
      color: var(--text-secondary);
    }
  }

  // 操作包装器
  .action-wrapper {
    flex-shrink: 0;
    align-self: center;
  }

  // 进度条包装器 - 增强版
  .progress-wrapper {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 6px;
    background: linear-gradient(90deg, var(--border-lighter) 0%, rgba(var(--border-lighter), 0.5) 100%);
    overflow: hidden;

    :deep(.el-progress) {
      line-height: 6px;

      .el-progress-bar__outer {
        height: 6px !important;
        background: transparent;
      }

      .el-progress-bar__inner {
        border-radius: 0;
        position: relative;
        overflow: hidden;

        // 添加流光效果
        &::after {
          content: '';
          position: absolute;
          top: 0;
          left: 0;
          height: 100%;
          width: 30%;
          background: linear-gradient(
                  90deg,
                  transparent,
                  rgba(255, 255, 255, 0.4),
                  transparent
          );
          animation: progressShine 2s infinite;
        }
      }
    }

    @keyframes progressShine {
      0% {
        left: -30%;
      }
      100% {
        left: 100%;
      }
    }
  }

  // 没有进度条时的占位
  &:not(:has(.progress-wrapper)) {
    padding-bottom: calc(#{tokens.$spacing-5} + 6px);
  }

  // 不同类型的样式 - 增强版
  &.status-primary {
    color: tokens.$brand-primary;

    .card-bg-decoration {
      color: tokens.$brand-primary;
    }

    .icon-wrapper .status-icon {
      background: linear-gradient(135deg, tokens.$brand-primary 0%, tokens.$brand-secondary 100%);
    }

    &::after {
      content: '';
      position: absolute;
      top: -2px;
      left: -2px;
      right: -2px;
      bottom: -2px;
      background: linear-gradient(45deg, tokens.$brand-primary, tokens.$brand-secondary);
      border-radius: tokens.$radius-xl;
      opacity: 0;
      z-index: -1;
      transition: opacity tokens.$duration-base;
    }

    &:hover::after {
      opacity: 0.15;
    }
  }

  &.status-success {
    color: tokens.$color-success;

    .card-bg-decoration {
      color: tokens.$color-success;
    }

    .icon-wrapper .status-icon {
      background: linear-gradient(135deg, tokens.$color-success 0%, tokens.$color-success-dark 100%);
    }
  }

  &.status-warning {
    color: tokens.$color-warning;

    .card-bg-decoration {
      color: tokens.$color-warning;
    }

    .icon-wrapper .status-icon {
      background: linear-gradient(135deg, tokens.$color-warning 0%, tokens.$color-warning-dark 100%);
    }
  }

  &.status-danger {
    color: tokens.$color-danger;

    .card-bg-decoration {
      color: tokens.$color-danger;
    }

    .icon-wrapper .status-icon {
      background: linear-gradient(135deg, tokens.$color-danger 0%, tokens.$color-danger-dark 100%);
    }
  }

  &.status-info {
    color: tokens.$color-info;

    .card-bg-decoration {
      color: tokens.$color-info;
    }

    .icon-wrapper .status-icon {
      background: linear-gradient(135deg, tokens.$color-info 0%, tokens.$color-info-dark 100%);
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
@media (max-width: tokens.$breakpoint-md) {
  .status-card {
    padding: tokens.$spacing-4;

    .card-content {
      flex-direction: column;

      .icon-wrapper {
        margin-bottom: tokens.$spacing-3;
      }
    }
  }
}
</style>
