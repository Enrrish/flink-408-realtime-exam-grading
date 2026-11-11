-- ============================================================
-- 408 在线模考系统 · 题库与组卷表结构
-- MySQL 8.0 / utf8mb4
-- 设计要点：
--   1. MySQL 是题库的唯一真相源，Redis 仅作 Flink 维表副本
--   2. 知识点为树形结构，题目与知识点是多对多（主考点 / 次考点）
--   3. 选项存 JSON，不单独建表（固定 4 项，避免组卷多表 JOIN）
--   4. 大题的小问独立成表，复核按小问给分
--   5. 组卷时把分值快照到 exam_question，题库改分不影响已发布试卷
-- ============================================================

SET NAMES utf8mb4;

-- ------------------------------------------------------------
-- 1. 知识点维度（树形）
-- ------------------------------------------------------------
DROP TABLE IF EXISTS knowledge_point;
CREATE TABLE knowledge_point (
  id         INT UNSIGNED NOT NULL AUTO_INCREMENT,
  parent_id  INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '0 表示一级',
  subject    TINYINT      NOT NULL COMMENT '1数据结构 2组成原理 3操作系统 4计算机网络',
  code       VARCHAR(32)  NOT NULL COMMENT '如 DS.TREE.BT',
  name       VARCHAR(64)  NOT NULL,
  level      TINYINT      NOT NULL DEFAULT 1,
  sort_no    INT          NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  UNIQUE KEY uk_code (code),
  KEY idx_parent (parent_id),
  KEY idx_subject (subject)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='知识点树';

-- ------------------------------------------------------------
-- 2. 题目主表
-- ------------------------------------------------------------
DROP TABLE IF EXISTS question;
CREATE TABLE question (
  id         INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  subject    TINYINT       NOT NULL COMMENT '同 knowledge_point.subject',
  qtype      TINYINT       NOT NULL DEFAULT 1 COMMENT '1单选 2综合应用题',
  stem       MEDIUMTEXT    NOT NULL COMMENT 'Markdown + LaTeX，图片以 ![](/img/xx.png) 引用',
  options    JSON          NULL     COMMENT '[{"key":"A","content":"..."},...] 仅单选',
  answer     VARCHAR(16)   NULL     COMMENT '单选题填 A/B/C/D；大题见 question_sub',
  analysis   TEXT          NULL     COMMENT '解析，答卷回顾用',
  difficulty TINYINT       NOT NULL DEFAULT 3 COMMENT '1~5',
  score      DECIMAL(4,1)  NOT NULL DEFAULT 2.0,
  source     VARCHAR(64)   NULL     COMMENT '来源，如 2023-408-15 / 自建',
  status     TINYINT       NOT NULL DEFAULT 1 COMMENT '1启用 0停用',
  created_at DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_pick (subject, qtype, status, difficulty),
  KEY idx_source (source)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='题目';

-- ------------------------------------------------------------
-- 3. 题目-知识点关联（主考点 weight=1.0，次考点 0.5）
-- ------------------------------------------------------------
DROP TABLE IF EXISTS question_knowledge;
CREATE TABLE question_knowledge (
  question_id        INT UNSIGNED NOT NULL,
  knowledge_point_id INT UNSIGNED NOT NULL,
  weight             DECIMAL(3,2) NOT NULL DEFAULT 1.00,
  PRIMARY KEY (question_id, knowledge_point_id),
  KEY idx_kp (knowledge_point_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='题目知识点关联';

-- ------------------------------------------------------------
-- 4. 大题小问（综合应用题的 (1)(2)(3)）
-- ------------------------------------------------------------
DROP TABLE IF EXISTS question_sub;
CREATE TABLE question_sub (
  id          INT UNSIGNED NOT NULL AUTO_INCREMENT,
  question_id INT UNSIGNED NOT NULL,
  seq         TINYINT      NOT NULL COMMENT '第几小问，从 1 开始',
  stem        TEXT         NOT NULL,
  answer      TEXT         NULL COMMENT '参考答案',
  rubric      JSON         NULL COMMENT '采分点 [{"point":"...","score":2}]，规则辅助打分用',
  score       DECIMAL(4,1) NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_q_seq (question_id, seq),
  KEY idx_q (question_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='大题小问';

-- ------------------------------------------------------------
-- 5. 考试（试卷）
-- ------------------------------------------------------------
DROP TABLE IF EXISTS exam;
CREATE TABLE exam (
  id           INT UNSIGNED NOT NULL AUTO_INCREMENT,
  title        VARCHAR(128) NOT NULL,
  start_at     DATETIME     NOT NULL,
  end_at       DATETIME     NOT NULL,
  duration_min INT          NOT NULL DEFAULT 180,
  total_score  DECIMAL(5,1) NOT NULL DEFAULT 150.0,
  status       TINYINT      NOT NULL DEFAULT 0 COMMENT '0草稿 1已发布 2进行中 3已结束',
  created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_status_start (status, start_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='考试';

-- ------------------------------------------------------------
-- 6. 组卷明细（分值快照，避免题库改动影响历史试卷）
-- ------------------------------------------------------------
DROP TABLE IF EXISTS exam_question;
CREATE TABLE exam_question (
  exam_id     INT UNSIGNED NOT NULL,
  question_id INT UNSIGNED NOT NULL,
  seq         SMALLINT     NOT NULL COMMENT '卷面题号 1~47',
  score       DECIMAL(4,1) NOT NULL COMMENT '本卷中该题分值（快照）',
  PRIMARY KEY (exam_id, question_id),
  UNIQUE KEY uk_seq (exam_id, seq)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='组卷明细';

-- ============================================================
-- 初始化数据：408 考纲二级知识点
-- ============================================================
INSERT INTO knowledge_point (id, parent_id, subject, code, name, level, sort_no) VALUES
(1,  0, 1, 'DS',            '数据结构',         1, 1),
(2,  1, 1, 'DS.LIST',       '线性表',           2, 1),
(3,  1, 1, 'DS.STACK',      '栈、队列和数组',    2, 2),
(4,  1, 1, 'DS.TREE',       '树与二叉树',       2, 3),
(5,  1, 1, 'DS.GRAPH',      '图',               2, 4),
(6,  1, 1, 'DS.SEARCH',     '查找',             2, 5),
(7,  1, 1, 'DS.SORT',       '排序',             2, 6),
(8,  4, 1, 'DS.TREE.BT',    '二叉树的遍历',      3, 1),
(9,  4, 1, 'DS.TREE.HUFF',  '哈夫曼树与编码',    3, 2),

(10, 0, 2, 'CO',            '计算机组成原理',    1, 2),
(11, 10,2, 'CO.OVERVIEW',   '计算机系统概述',    2, 1),
(12, 10,2, 'CO.DATA',       '数据的表示和运算',   2, 2),
(13, 10,2, 'CO.MEMORY',     '存储器层次结构',    2, 3),
(14, 10,2, 'CO.ISA',        '指令系统',         2, 4),
(15, 10,2, 'CO.CPU',        '中央处理器',       2, 5),
(16, 10,2, 'CO.IO',         '总线和输入输出系统', 2, 6),
(17, 13,2, 'CO.MEMORY.CACHE','Cache 与虚拟存储', 3, 1),

(18, 0, 3, 'OS',            '操作系统',         1, 3),
(19, 18,3, 'OS.OVERVIEW',   '操作系统概述',      2, 1),
(20, 18,3, 'OS.PROCESS',    '进程管理',         2, 2),
(21, 18,3, 'OS.MEMORY',     '内存管理',         2, 3),
(22, 18,3, 'OS.FILE',       '文件管理',         2, 4),
(23, 18,3, 'OS.IO',         '输入输出管理',      2, 5),
(24, 21,3, 'OS.MEMORY.PR',  '页面置换算法',      3, 1),

(25, 0, 4, 'NET',           '计算机网络',        1, 4),
(26, 25,4, 'NET.ARCH',      '体系结构',         2, 1),
(27, 25,4, 'NET.PHY',       '物理层',           2, 2),
(28, 25,4, 'NET.LINK',      '数据链路层',        2, 3),
(29, 25,4, 'NET.IP',        '网络层',           2, 4),
(30, 25,4, 'NET.TCP',       '传输层',           2, 5),
(31, 25,4, 'NET.APP',       '应用层',           2, 6),
(32, 27,4, 'NET.PHY.SHANNON','香农定理与奈奎斯特', 3, 1);

-- ============================================================
-- 样例题（5 道，覆盖四个科目，验证 JSON 选项与标签关联）
-- 仅用于验证表结构，正式题库请从真题仓库解析或用脚本生成
-- ============================================================
INSERT INTO question (id, subject, qtype, stem, options, answer, analysis, difficulty, score, source) VALUES
(1, 1, 1,
 '设某算法的时间复杂度递推式为 T(n) = 2T(n/2) + O(n)，且 T(1) = O(1)，则 T(n) = （　）。',
 '[{"key":"A","content":"O(n)"},{"key":"B","content":"O(n log n)"},{"key":"C","content":"O(n^2)"},{"key":"D","content":"O(log n)"}]',
 'B',
 '符合主定理第二种情形：a=2, b=2, f(n)=O(n)，因 f(n) 与 n^(log_b a)=n 同阶，故 T(n)=O(n log n)。归并排序即此形态。',
 3, 2.0, '自建'),

(2, 1, 1,
 '一棵有 1000 个结点的完全二叉树，其叶子结点的个数为（　）。',
 '[{"key":"A","content":"250"},{"key":"B","content":"500"},{"key":"C","content":"501"},{"key":"D","content":"512"}]',
 'B',
 '完全二叉树中度为 1 的结点至多 1 个。由 n0 = n2 + 1 及 n0 + n1 + n2 = 1000，n1 取 1 时解得 n0 = 500。',
 3, 2.0, '自建'),

(3, 2, 1,
 '某计算机主存地址为 32 位，按字节编址。Cache 数据区共 512 行，每行 64B，采用直接映射方式，则标记（tag）字段的位数为（　）。',
 '[{"key":"A","content":"15"},{"key":"B","content":"17"},{"key":"C","content":"19"},{"key":"D","content":"21"}]',
 'B',
 '块内地址 6 位（64B），行号 9 位（512 行），标记 = 32 - 6 - 9 = 17 位。',
 4, 2.0, '自建'),

(4, 3, 1,
 '某进程的页面引用串为 7, 0, 1, 2, 0, 3, 0, 4，系统分配 3 个页框，采用 LRU 置换算法，则缺页次数为（　）。',
 '[{"key":"A","content":"5"},{"key":"B","content":"6"},{"key":"C","content":"7"},{"key":"D","content":"8"}]',
 'B',
 '依次装入 7、0、1 均缺页；访问 2 淘汰 7；访问 0 命中；访问 3 淘汰 1；访问 0 命中；访问 4 淘汰 2。共缺页 6 次。',
 3, 2.0, '自建'),

(5, 4, 1,
 '某信道带宽为 3kHz，信噪比为 30dB，根据香农定理，该信道的最大数据传输速率约为（　）。',
 '[{"key":"A","content":"3 kb/s"},{"key":"B","content":"6 kb/s"},{"key":"C","content":"30 kb/s"},{"key":"D","content":"60 kb/s"}]',
 'C',
 '30dB 对应 S/N = 1000，C = 3000 × log2(1+1000) ≈ 3000 × 9.97 ≈ 29.9 kb/s。',
 4, 2.0, '自建');

INSERT INTO question_knowledge (question_id, knowledge_point_id, weight) VALUES
(1, 7,   1.00), (1, 1,   0.50),
(2, 4,   1.00), (2, 8,   0.50),
(3, 17,  1.00), (3, 13,  0.50),
(4, 24,  1.00), (4, 21,  0.50),
(5, 32,  1.00), (5, 27,  0.50);

-- ============================================================
-- 组卷示例：随机抽 10 道数据结构的单选题
-- 注：题量在千级时 ORDER BY RAND() 可接受；若涨到十万级需改用
--     随机 id 区间法或预生成抽题序列
-- ============================================================
-- INSERT INTO exam_question (exam_id, question_id, seq, score)
-- SELECT 1, id, ROW_NUMBER() OVER (ORDER BY id), 2.0
-- FROM (SELECT id FROM question
--       WHERE subject = 1 AND qtype = 1 AND status = 1
--       ORDER BY RAND() LIMIT 10) t;
