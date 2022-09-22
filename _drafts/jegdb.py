# -*- coding: UTF-8 -*-
# jemalloc 5.2.0
# python2.7
#
# Some gdb python scripts used to obtain jemalloc metadata.
#
# Usage:
#   gdb> pi
#   gdb> >>> import sys
#   gdb> >>> sys.path.append('.')
#   gdb> >>> import jegdb
#   gdb> >>> jegdb.find(0x7fe20cc44000, 0x7fe20cc46000, 8)
#   gdb> [140608853448544]
#
import gdb
UINT64_MAX = (2 ** 64) - 1
LG_VADDR = 48
LG_SIZEOF_PTR = 3
LG_PAGE = 12
MALLOCX_ARENA_BITS = 12
SC_LG_TINY_MIN = 3
LG_SLAB_MAXREGS = LG_PAGE - SC_LG_TINY_MIN

RTREE_NHIB = ((1 << (LG_SIZEOF_PTR+3)) - LG_VADDR)
RTREE_NLIB = LG_PAGE
RTREE_NSB = LG_VADDR - RTREE_NLIB
RTREE_HEIGHT = 2


class rtree_level_t(object):
  def __init__(self, bits, cumbits):
    self.bits = bits
    self.cumbits = cumbits


rtree_levels = [
  rtree_level_t(RTREE_NSB//2, RTREE_NHIB + RTREE_NSB//2),
  rtree_level_t(RTREE_NSB//2 + RTREE_NSB%2, RTREE_NHIB + RTREE_NSB)
]

# 等同于 c/c++ 中 op1 << op2, op1: u64
# 不能直接使用 python op1 << op2, 主要是 python 支持大整数...
# 若 op1 << op2 不会在 u64 下不会有溢出, 则 python << 等同于 c.
def c_u64_left_shift(op1, op2):
  return (op1 << op2) & ((2 ** 64) - 1)

# key: int, level: int
# ret: int
def rtree_subkey(key, level):
  ptrbits = 1 << (LG_SIZEOF_PTR+3)
  cumbits = rtree_levels[level].cumbits
  shiftbits = ptrbits - cumbits
  maskbits = rtree_levels[level].bits
  mask = (1 << maskbits) - 1
  return ((key >> shiftbits) & mask)

# arr_addr, int, 数组首地址.
# idx, int,
# typ, gdb.Type, 指定了数组元素的类型
# ret, gdb.Value, typ 类型.
def array_at(arr_addr, idx, typ):
  return gdb.Value(arr_addr + idx * typ.sizeof).cast(typ.pointer()).dereference()

def elem_ptr(arr_addr, idx, typ):
  return gdb.Value(arr_addr + idx * typ.sizeof).cast(typ.pointer())

# rtree, gdb.Value, rtree_t 类型.
# key, int
def rtree_leaf_elm_lookup_hard(rtree, key):
  node = rtree['root']
  subkey0 = rtree_subkey(key, 0)
  subkey1 = rtree_subkey(key, 1)
  leaf = int(array_at(int(node.address), subkey0, gdb.lookup_type('struct rtree_node_elm_s'))['child']['repr'])
  return array_at(leaf, subkey1, gdb.lookup_type('struct rtree_leaf_elm_s'))['le_bits']['repr']

extents_rtree = gdb.lookup_global_symbol('je_extents_rtree').value()

def rtree_lookup(key):
  return rtree_leaf_elm_lookup_hard(extents_rtree, key)

def MASK(w, s):
  return c_u64_left_shift(c_u64_left_shift(1, w) - 1, s)

EXTENT_BITS_ARENA_WIDTH = MALLOCX_ARENA_BITS
EXTENT_BITS_ARENA_SHIFT = 0
EXTENT_BITS_ARENA_MASK = MASK(EXTENT_BITS_ARENA_WIDTH, EXTENT_BITS_ARENA_SHIFT)

EXTENT_BITS_SLAB_WIDTH = 1
EXTENT_BITS_SLAB_SHIFT = (EXTENT_BITS_ARENA_WIDTH + EXTENT_BITS_ARENA_SHIFT)
EXTENT_BITS_SLAB_MASK = MASK(EXTENT_BITS_SLAB_WIDTH, EXTENT_BITS_SLAB_SHIFT)

EXTENT_BITS_COMMITTED_WIDTH = 1
EXTENT_BITS_COMMITTED_SHIFT = (EXTENT_BITS_SLAB_WIDTH + EXTENT_BITS_SLAB_SHIFT)
EXTENT_BITS_COMMITTED_MASK = MASK(EXTENT_BITS_COMMITTED_WIDTH, EXTENT_BITS_COMMITTED_SHIFT)

EXTENT_BITS_DUMPABLE_WIDTH = 1
EXTENT_BITS_DUMPABLE_SHIFT = (EXTENT_BITS_COMMITTED_WIDTH + EXTENT_BITS_COMMITTED_SHIFT)
EXTENT_BITS_DUMPABLE_MASK = MASK(EXTENT_BITS_DUMPABLE_WIDTH, EXTENT_BITS_DUMPABLE_SHIFT)

EXTENT_BITS_ZEROED_WIDTH = 1
EXTENT_BITS_ZEROED_SHIFT = (EXTENT_BITS_DUMPABLE_WIDTH + EXTENT_BITS_DUMPABLE_SHIFT)
EXTENT_BITS_ZEROED_MASK = MASK(EXTENT_BITS_ZEROED_WIDTH, EXTENT_BITS_ZEROED_SHIFT)

EXTENT_BITS_STATE_WIDTH = 2
EXTENT_BITS_STATE_SHIFT = (EXTENT_BITS_ZEROED_WIDTH + EXTENT_BITS_ZEROED_SHIFT)
EXTENT_BITS_STATE_MASK = MASK(EXTENT_BITS_STATE_WIDTH, EXTENT_BITS_STATE_SHIFT)

EXTENT_BITS_SZIND_WIDTH = 8 # LG_CEIL(SC_NSIZES)
EXTENT_BITS_SZIND_SHIFT = (EXTENT_BITS_STATE_WIDTH + EXTENT_BITS_STATE_SHIFT)
EXTENT_BITS_SZIND_MASK = MASK(EXTENT_BITS_SZIND_WIDTH, EXTENT_BITS_SZIND_SHIFT)

EXTENT_BITS_NFREE_WIDTH = (LG_SLAB_MAXREGS + 1)
EXTENT_BITS_NFREE_SHIFT = (EXTENT_BITS_SZIND_WIDTH + EXTENT_BITS_SZIND_SHIFT)
EXTENT_BITS_NFREE_MASK = MASK(EXTENT_BITS_NFREE_WIDTH, EXTENT_BITS_NFREE_SHIFT)

EXTENT_BITS_BINSHARD_WIDTH = 6
EXTENT_BITS_BINSHARD_SHIFT = (EXTENT_BITS_NFREE_WIDTH + EXTENT_BITS_NFREE_SHIFT)
EXTENT_BITS_BINSHARD_MASK = MASK(EXTENT_BITS_BINSHARD_WIDTH, EXTENT_BITS_BINSHARD_SHIFT)

EXTENT_BITS_SN_SHIFT = (EXTENT_BITS_BINSHARD_WIDTH + EXTENT_BITS_BINSHARD_SHIFT)
# EXTENT_BITS_SN_MASK = (UINT64_MAX << EXTENT_BITS_SN_SHIFT)
EXTENT_BITS_SN_MASK = c_u64_left_shift(UINT64_MAX, EXTENT_BITS_SN_SHIFT)

# val, int
def desc_e_bits(e_bits):
  print("arena_ind = %s" % ((e_bits & EXTENT_BITS_ARENA_MASK) >> EXTENT_BITS_ARENA_SHIFT))
  print("slab = %s" % ((e_bits & EXTENT_BITS_SLAB_MASK) >> EXTENT_BITS_SLAB_SHIFT))
  print("committed = %s" % ((e_bits & EXTENT_BITS_COMMITTED_MASK) >> EXTENT_BITS_COMMITTED_SHIFT))
  print("dumpable = %s" % ((e_bits & EXTENT_BITS_DUMPABLE_MASK) >> EXTENT_BITS_DUMPABLE_SHIFT))
  print("zeroed = %s" % ((e_bits & EXTENT_BITS_ZEROED_MASK) >> EXTENT_BITS_ZEROED_SHIFT))
  print("state = %s" % ((e_bits & EXTENT_BITS_STATE_MASK) >> EXTENT_BITS_STATE_SHIFT))
  print("szind = %s" % ((e_bits & EXTENT_BITS_SZIND_MASK) >> EXTENT_BITS_SZIND_SHIFT))
  print("nfree = %s" % ((e_bits & EXTENT_BITS_NFREE_MASK) >> EXTENT_BITS_NFREE_SHIFT))
  print("bin_shard = %s" % ((e_bits & EXTENT_BITS_BINSHARD_MASK) >> EXTENT_BITS_BINSHARD_SHIFT))
  print("sn = %s" % ((e_bits & EXTENT_BITS_SN_MASK) >> EXTENT_BITS_SN_SHIFT))

# val, int
# return gdb.Value, extent_t 类型
def rtree_leaf_elm_bits_extent_get(val):
  ptr = ((c_u64_left_shift(val, RTREE_NHIB) >> RTREE_NHIB) >> 1) << 1
  if ptr == 0:
    return None
  return gdb.Value(ptr).cast(gdb.lookup_type('struct extent_s').pointer()).dereference()

# cb 调用形式, Fn(val) -> bool;
#  val, gdb.Value, extent_s 类型.
#  return true, 继续遍历.
def traverse_extent(cb):
  prev_elem_ptr = 0
  ARRAY_SIZE = 1 << (RTREE_NSB/RTREE_HEIGHT)
  TYPE_RTREE_NODE_ELM_S = gdb.lookup_type('struct rtree_node_elm_s')
  TYPE_RTREE_LEAF_ELM_S = gdb.lookup_type('struct rtree_leaf_elm_s')
  nodeaddr = extents_rtree['root'].address
  for i in xrange(0, ARRAY_SIZE):
    leaf_ptr = int(array_at(int(nodeaddr), i, TYPE_RTREE_NODE_ELM_S)['child']['repr'])
    if leaf_ptr == 0:
      continue
    for j in xrange(0, ARRAY_SIZE):
      elem_ptr = int(array_at(leaf_ptr, j, TYPE_RTREE_LEAF_ELM_S)['le_bits']['repr'])
      elem = rtree_leaf_elm_bits_extent_get(elem_ptr)
      if elem_ptr == 0 or elem is None:
        continue
      if int(elem.address) == prev_elem_ptr:
        continue
      if not cb(elem):
        return
      prev_elem_ptr = int(elem.address)
  return

def PAGE_ADDR2BASE(val):
  return (val >> LG_PAGE) << LG_PAGE

def extent_size_get(extent):
  return (int(extent['e_size_esn']) >> LG_PAGE) << LG_PAGE

def extent_arena_ind_get(extent):
  return (int(extent['e_bits']) & EXTENT_BITS_ARENA_MASK) >> EXTENT_BITS_ARENA_SHIFT

def find_traverse_cb(extent, left, right, bitwidth, arena_ind, retlist):
  if arena_ind is not None and extent_arena_ind_get(extent) != arena_ind:
    return
  extent_base = PAGE_ADDR2BASE(int(extent['e_addr']))
  extent_size = extent_size_get(extent)
  inttype = None
  extent_n = 0
  if bitwidth == 1:
    inttype = gdb.lookup_type('unsigned char')
    extent_n = extent_size
  elif bitwidth == -1:
    inttype = gdb.lookup_type('signed char')
    extent_n = extent_size
  elif bitwidth == 2:
    inttype = gdb.lookup_type('unsigned short')
    extent_n = extent_size / 2
  elif bitwidth == -2:
    inttype = gdb.lookup_type('signed short')
    extent_n = extent_size / 2
  elif bitwidth == 4:
    inttype = gdb.lookup_type('unsigned int')
    extent_n = extent_size / 4
  elif bitwidth == -4:
    inttype = gdb.lookup_type('signed int')
    extent_n = extent_size / 4
  elif bitwidth == 8:
    inttype = gdb.lookup_type('unsigned long')
    extent_n = extent_size / 8
  elif bitwidth == -8:
    inttype = gdb.lookup_type('signed long')
    extent_n = extent_size / 8
  else:
    raise RuntimeError('bad bitwidth')

  for i in xrange(0, extent_n):
    intvalptr = elem_ptr(extent_base, i, inttype)
    intval = int(intvalptr.dereference())
    if intval >= left and intval <= right:
      retlist.append(int(intvalptr))
  return True

# 找到位于 [find, right] 之间的值, 并返回它的地址.
# arena_ind 若不为 None, 则只在 e_bits.arena_ind = arena_ind edata 中寻找.
# sizechar 取值 1, 2, 4, 8; -1, -2, -4, -8.
# return [int], 每个元素表示地址.
def find(left, right, sizechar, arena_ind=None):
  ret = []
  traverse_extent(lambda e: find_traverse_cb(e, left, right, sizechar, arena_ind, ret))
  return ret
