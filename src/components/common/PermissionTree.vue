<!--
  ──────────────────────────────────────────
  权限树选择组件（递归）
  用于角色编辑时可视化分配权限，支持无限层级。
  每层自动缩进，MENU 节点可折叠，勾选后显示允许/拒绝。
  ──────────────────────────────────────────
-->

<script setup>
const props = defineProps({
  treeData: { type: Array, default: () => [] },
  checkedPermissions: { type: Map, default: () => new Map() },
  depth: { type: Number, default: 0 },
})

const emit = defineEmits(['update'])

function toggleCheck(permId) {
  const newMap = new Map(props.checkedPermissions)
  const cur = newMap.get(permId) || { checked: false, is_deny: false }
  newMap.set(permId, { ...cur, checked: !cur.checked })
  emit('update', newMap)
}

function setDeny(permId, isDeny) {
  const newMap = new Map(props.checkedPermissions)
  const cur = newMap.get(permId) || { checked: false, is_deny: false }
  newMap.set(permId, { ...cur, is_deny: isDeny })
  emit('update', newMap)
}

function isChecked(permId) {
  return props.checkedPermissions.get(permId)?.checked || false
}

function isDeny(permId) {
  return props.checkedPermissions.get(permId)?.is_deny || false
}
</script>

<template>
  <div class="perm-tree">
    <template v-for="node in treeData" :key="node.id">
      <div class="perm-tree-node" :style="{ paddingLeft: depth * 24 + 'px' }">
        <div class="perm-tree-row">
          <!-- MENU 类型仅展示，不可勾选（菜单权限由子按钮权限自动派生） -->
          <template v-if="node.type === 'MENU'">
            <span class="perm-name perm-menu-name">{{ node.name }}</span>
            <el-tag size="small" type="primary" class="perm-tag">菜单</el-tag>
            <span class="perm-menu-hint">（自动）</span>
          </template>
          <!-- BUTTON 类型可勾选 -->
          <el-checkbox
            v-else
            :model-value="isChecked(node.id)"
            @change="toggleCheck(node.id)"
          >
            <span class="perm-name">{{ node.name }}</span>
            <el-tag size="small" type="info" class="perm-tag">按钮</el-tag>
          </el-checkbox>
          <template v-if="node.type !== 'MENU' && isChecked(node.id)">
            <el-radio-group
              :model-value="isDeny(node.id)"
              size="small"
              @change="(val) => setDeny(node.id, val)"
            >
              <el-radio :value="false">允许</el-radio>
              <el-radio :value="true">拒绝</el-radio>
            </el-radio-group>
          </template>
        </div>
        <!-- 递归渲染子节点 -->
        <PermissionTree
          v-if="node.children && node.children.length"
          :tree-data="node.children"
          :checked-permissions="checkedPermissions"
          :depth="depth + 1"
          @update="(val) => emit('update', val)"
        />
      </div>
    </template>
  </div>
</template>

<style scoped>
.perm-tree {
  width: 100%;
}
.perm-tree-node {
  margin-bottom: 2px;
}
.perm-tree-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 8px;
  border-bottom: 1px solid #f2f2f2;
}
.perm-tree-row:hover {
  background: #f5f7fa;
}
.perm-name {
  margin-right: 8px;
  font-size: 14px;
}
.perm-tag {
  margin-left: 4px;
}
.perm-menu-name {
  color: #409eff;
}
.perm-menu-hint {
  font-size: 12px;
  color: #909399;
  margin-left: 8px;
}
</style>
