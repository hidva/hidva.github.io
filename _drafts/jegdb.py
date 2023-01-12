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
import re, bisect, sys

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

def extent_slab_get(extent):
  e_bits = int(extent['e_bits'])
  return ((e_bits & EXTENT_BITS_SLAB_MASK) >> EXTENT_BITS_SLAB_SHIFT) != 0

def extent_szind_get(extent):
  e_bits = int(extent['e_bits'])
  return (e_bits & EXTENT_BITS_SZIND_MASK) >> EXTENT_BITS_SZIND_SHIFT

def extent_addr_get(extent):
  return int(extent['e_addr'])

extent_state_active   = 0
extent_state_dirty    = 1
extent_state_muzzy    = 2
extent_state_retained = 3
def extent_state_get(extent):
  e_bits = int(extent['e_bits'])
  return (e_bits & EXTENT_BITS_STATE_MASK) >> EXTENT_BITS_STATE_SHIFT

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

LG_SIZEOF_BITMAP = 3
LG_BITMAP_GROUP_NBITS = LG_SIZEOF_BITMAP + 3
BITMAP_GROUP_NBITS = 1 << LG_BITMAP_GROUP_NBITS
BITMAP_GROUP_NBITS_MASK = BITMAP_GROUP_NBITS-1
# bitmap_ptr, int, bitmap_t* 指针类型.
# ret True/False
def bitmap_get(bitmap_ptr, bit):
  goff = bit >> LG_BITMAP_GROUP_NBITS
  g = int(array_at(bitmap_ptr, goff, gdb.lookup_type('unsigned long')))
  return (g & c_u64_left_shift(1, (bit & BITMAP_GROUP_NBITS_MASK))) == 0


sz_index2size_tab = gdb.lookup_global_symbol('je_sz_index2size_tab').value()
# extent, gdb.Value, extent_t 类型.
# ptr, int,
# ret: (regind: int, regsize: int),
def arena_slab_regind(extent, ptr):
  assert extent_slab_get(extent)
  assert ptr >= extent_addr_get(extent)
  diff = ptr - extent_addr_get(extent)
  szind = extent_szind_get(extent)
  regsize = int(sz_index2size_tab[szind])
  return (diff // regsize, regsize)

# 若 ptr 指向内存块是 jemalloc 分配的, 那么返回内存块的首地址, 内存块的大小, 以及内存块是否处于 free 状态 is_free.
# ret, (small_size_class?, chunk_ptr, chunk_size, is_free)
# 若 is_free = false, 则意味着内存块尚未被 free, 或者被 free 了但位于 tcache 中, 对 jemalloc arena 系统尚不可见.
# 对于 large size class 由于 cache_oblivious 的存在, chunk_size 可能大于实际 size.
# ptr, int,
def ptr_info(ptr):
  ex = rtree_leaf_elm_bits_extent_get(int(rtree_lookup(ptr)))
  small_size_class = extent_slab_get(ex)
  chunk_ptr = extent_addr_get(ex)
  if small_size_class:
    regind, regsize = arena_slab_regind(ex, ptr)
    chunk_ptr = chunk_ptr + regind * regsize
    chunk_size = regsize
    is_free = not bitmap_get(int(ex['e_slab_data']['bitmap'].address), regind)
  else:
    chunk_size = extent_size_get(ex)
    is_free = extent_state_get(ex) != extent_state_active
  return (small_size_class, chunk_ptr, chunk_size, is_free)


# 输入: maintenance info sections
# 输出: 若干互不相交的地址区间
class Merger(object):
  def __init__(self):
    # self.data [(left, right)], 每一个元素表明 [left, right) 区间, 元素之间不相交, 并且按照 left 从小到大排序.
    self.data_l = []
    self.data_r = []

  # 若 [left, right) 表明的区间与 self.data 某一区间相交, 则合入该区间. 否则新插入到 self.data 中.
  def insert(self, left, right):
    idx = bisect.bisect_left(self.data_l, left)
    merge_l = idx > 0 and left <= self.data_r[idx - 1]
    merge_r = idx < len(self.data_l) and right >= self.data_l[idx]
    if not merge_l and not merge_r:
      self.data_l.insert(idx, left)
      self.data_r.insert(idx, right)
      return
    if merge_l and not merge_r:
      self.data_r[idx - 1] = max(right, self.data_r[idx - 1])
      return
    if not merge_l and merge_r:
      self.data_l[idx] = left
      self.data_r[idx] = max(right, self.data_r[idx])
      return
    # merge_l and merge_r
    self.data_r[idx - 1] = max(right, self.data_r[idx])
    self.data_l.pop(idx)
    self.data_r.pop(idx)
    return

# fileobj, 该文件中存放着 maintenance info sections 的输出.
# ret [(left, right)], 等同于 Merger::data.
def parse_info_sections(fileobj):
  PATTERN = re.compile(r'(0x[0-9a-f]+)->(0x[0-9a-f]+)\s+at\s+(0x[0-9a-f]+)')
  merger = Merger()
  for line in fileobj:
    line = line.strip()
    if not line:
      continue
    matchobj = PATTERN.search(line)
    if not matchobj:
      continue
    s_addr = int(matchobj.group(1), 0)
    e_addr = int(matchobj.group(2), 0)
    if s_addr >= e_addr:
      continue
    merger.insert(s_addr, e_addr)
  return [(merger.data_l[i], merger.data_r[i]) for i in xrange(0, len(merger.data_l))]

TCACHE_FIELD = 'cant_access_tsd_items_directly_use_a_getter_or_setter_tcache'

# head, int 类型, 实际类型 *tsd_t
# cb, 调用形式: Fn(val) -> bool
#   val, gdb.Value, tsd_t 类型.
#   RET, true, 继续遍历.
def do_traverse_tsd_list(head, cb):
  if head == 0:
    return
  TSD_T_TYPE = gdb.lookup_type('tsd_t')
  next = head
  nextobj = gdb.Value(next).cast(TSD_T_TYPE.pointer()).dereference()
  while True:
    if not cb(nextobj):
      break
    next = nextobj[TCACHE_FIELD]['tsd_link']['qre_next']
    if int(next) == head:
      break
    nextobj = next.dereference()
  return

def traverse_tsd_list(cb):
  h = int(gdb.parse_and_eval('tsd_nominal_tsds')['qlh_first'])
  do_traverse_tsd_list(h, cb)
  return

def ptr_eq(ptr1, ptr2, is_small):
  if is_small:
    return ptr1 == ptr2
  # cache_oblivious
  return PAGE_ADDR2BASE(ptr1) == PAGE_ADDR2BASE(ptr2)

# val, gdb.Value 类型, cache_bin_s 类型.
# ptr, int
# RET, [idx], -ncached <= idx <= -1
def cache_bin_find(cachebin, ptr, is_small):
  ret = []
  VOID_TYPE = gdb.lookup_type('void')
  avail = int(cachebin['avail'])
  ncached = int(cachebin['ncached'])
  for idx in xrange(-ncached, 0):
    val = int(array_at(avail, idx, VOID_TYPE.pointer()))
    if ptr_eq(val, ptr, is_small):
      ret.append(idx)
  return ret

SC_LG_NGROUP = 2
LG_QUANTUM = 4
SC_NGROUP = 1 << SC_LG_NGROUP
SC_PTR_BITS = ((1 << LG_SIZEOF_PTR) * 8)
SC_NTINY = (LG_QUANTUM - SC_LG_TINY_MIN)
SC_NPSEUDO = SC_NGROUP
SC_LG_FIRST_REGULAR_BASE = (LG_QUANTUM + SC_LG_NGROUP)
SC_LG_BASE_MAX = (SC_PTR_BITS - 2)
SC_NREGULAR = (SC_NGROUP * (SC_LG_BASE_MAX - SC_LG_FIRST_REGULAR_BASE + 1) - 1)
SC_NSIZES = (SC_NTINY + SC_NPSEUDO + SC_NREGULAR)
SC_NBINS = (SC_NTINY + SC_NPSEUDO + SC_NGROUP * (LG_PAGE + SC_LG_NGROUP - SC_LG_FIRST_REGULAR_BASE) - 1)
# tsd, gdb.Value, tsd_t 类型.
# ptr, int 类型.
# 若在 tsd tcache 中找到了 ptr, 则返回 [(is_small, idx, [cache_idx])].
#  is_small 为 true 意味着 bins_small, 否则 bins_large.
#  idx 为 bins_small/bins_large 下标.
def tcache_find(tsd, ptr):
  ret = []
  tcache = tsd[TCACHE_FIELD]
  CACHE_BIN_T_TYPE = gdb.lookup_type('cache_bin_t')
  for idx in xrange(0, SC_NBINS):
    cache_idx = cache_bin_find(tcache['bins_small'][idx], ptr, True)
    if len(cache_idx) > 0:
      ret.append((True, idx, cache_idx))
  for idx in xrange(0, SC_NSIZES - SC_NBINS):
    cache_idx = cache_bin_find(tcache['bins_large'][idx], ptr, False)
    if len(cache_idx) > 0:
      ret.append((False, idx, cache_idx))
  return ret

# ptr, int 类型.
# RET: [(tsd, [(is_small, idx, [cache_idx])])]
def all_tcache_find(ptr):
  ret = []
  def tsd_find(tsd):
    find_ret = tcache_find(tsd, ptr)
    if len(find_ret) > 0:
      ret.append((tsd, find_ret))
    return True
  traverse_tsd_list(tsd_find)
  return ret
