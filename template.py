"""
Day 14 — AI Evaluation & Benchmarking Pipeline
AICB-P1: AI Practical Competency Program, Phase 1

Key concepts from lecture:
    - Evaluation = Scientific Method for AI (Hypothesis → Experiment → Measure → Conclude → Iterate)
    - 4 nhóm metrics: Task Completion, Answer Quality, RAG-Specific, Business
    - RAG pipeline metrics: Context Recall → Context Precision → Faithfulness → Answer Relevancy
    - LLM-as-Judge: rubric scoring 1-5, detect bias (positional, verbosity, self-preference)
    - Golden dataset: stratified sampling (5 Easy + 7 Medium + 5 Hard + 3 Adversarial)
    - Failure taxonomy: hallucination, irrelevant, incomplete, off_topic, refusal
    - 5 Whys method for root cause analysis
    - CI/CD integration: eval as quality gate (score < threshold = block deploy)
    - Continuous Improvement Loop: Evaluate → Analyze → Improve → Augment → Repeat

Instructions:
    1. Fill in every required section marked with TODO.
    2. Do NOT change class/function signatures. The optional ``contexts``
       parameter in ``run_full_eval`` is part of the required interface.
    3. Copy this file to solution/solution.py when done.
    4. Run: pytest tests/ -v

The reranking helper is an optional bonus exercise and may remain unimplemented.
"""

from __future__ import annotations
import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable

# ---------------------------------------------------------------------------
# Task 1 — Data Models (Golden Dataset + Evaluation Results)
# ---------------------------------------------------------------------------


@dataclass
class QAPair:
    """
    A question-answer pair for evaluation (part of the Golden Dataset).

    From lecture: Golden dataset cần có:
        - question: câu hỏi user
        - ground_truth (expected_answer): expert-written expected answer
        - context: source documents cần retrieve
        - metadata: difficulty (easy/medium/hard), category, source_docs

    Fields:
        question:        The question to answer.
        expected_answer: The reference/ground-truth answer (expert-written).
        context:            Source context (may be empty string if not applicable).
        metadata:           Optional metadata dict (difficulty, category, etc.).
        retrieved_contexts: List of retrieved chunks (ORDER = retriever rank).
                            Used by the retrieval-side metrics (Task 2b).
    """

    # TODO: define fields
    # --- Field BẮT BUỘC (không có mặc định) - phải đứng trước ---
    question: str  # câu hỏi của khách hàng, VD "How long is the warranty?"
    expected_answer: (
        str  # đáp án chuẩn do chuyên gia (là bạn) viết, dùng làm "đáp án đúng" để chấm
    )

    # --- Field TÙY CHỌN (có mặc định) - phải đứng sau ---
    context: str = (
        ""  # evidence chuẩn (gold context): đoạn văn trong corpus chứa đáp án
    )
    # "" = không có. Tests còn truyền None, Python không cấm nên vẫn chạy được

    metadata: dict = field(default_factory=dict)
    # thông tin phụ: id, difficulty, attack_type (evaluate_answers.py sẽ nhét vào đây)
    # dùng default_factory để mỗi QAPair có dict RIÊNG

    retrieved_contexts: list = field(default_factory=list)
    # các chunk mà retriever THỰC SỰ lấy ra cho câu hỏi này
    # THỨ TỰ trong list = thứ hạng của retriever (chunk đầu = xếp hạng 1)
    # Task 2b (Context Recall/Precision) sẽ dùng list này


@dataclass
class EvalResult:
    """
    Evaluation result for a single Q&A pair.

    From lecture - RAG metrics pipeline:
        Question → Retriever → Context → Generator → Answer
        Each step has a metric: Context Recall, Context Precision, Faithfulness, Answer Relevancy

    From lecture - Score interpretation:
        0.8-1.0: Good (Monitor, maintain)
        0.6-0.8: Needs work (Analyze failures, iterate)
        < 0.6: Significant issues (Deep investigation required)

    Fields:
        qa_pair:        The original QAPair.
        actual_answer:  What the agent actually returned.
        faithfulness:   Float 0-1, how grounded the answer is in context.
        relevance:      Float 0-1, how relevant the answer is to the question.
        completeness:   Float 0-1, how complete the answer is vs expected.
        passed:         True if all three scores >= 0.5.
        failure_type:   None if passed, otherwise one of:
                        "hallucination", "irrelevant", "incomplete", "off_topic".
        context_precision: Float 0-1 or None — quality of retrieval ranking.
        context_recall:    Float 0-1 or None — coverage of expected by context.
                        (Both stay None unless retrieved chunks are supplied;
                         they are NOT part of overall_score().)
    """

    # TODO: define fields
    # --- Field BẮT BUỘC: luôn có sau mỗi lần chấm ---
    qa_pair: QAPair  # câu hỏi gốc (giữ lại để sau này biết điểm này của câu nào)
    # evaluate_answers.py đọc result.qa_pair.metadata / .question => tên phải đúng
    actual_answer: str  # câu trả lời thật của chatbot
    faithfulness: float  # 0-1: câu trả lời có bám vào context không (0 = bịa)
    relevance: float  # 0-1: câu trả lời có đúng trọng tâm câu hỏi không
    completeness: float  # 0-1: câu trả lời có đủ ý so với expected_answer không
    passed: bool  # True nếu cả 3 điểm trên >= 0.5

    # --- Field TÙY CHỌN ---
    failure_type: str | None = None
    # None nếu passed; nếu rớt thì là "hallucination"/"irrelevant"/"incomplete"/"off_topic"
    # "str | None" nghĩa là "hoặc là chuỗi, hoặc là None"

    context_precision: float | None = None  # điểm chất lượng xếp hạng của retriever
    context_recall: float | None = None  # điểm độ phủ của retriever
    # Hai điểm này là None khi không có danh sách chunk để chấm.
    # Chúng chỉ để CHẨN ĐOÁN retriever, KHÔNG tính vào overall_score()

    def overall_score(self) -> float:
        """Compute the average of faithfulness, relevance, and completeness.

        Returns:
            (faithfulness + relevance + completeness) / 3.0

        TODO: Return mean of the three metric scores
        """
        # Trung bình cộng của 3 metric phía câu trả lời.
        # Chia cho 3.0 (số thực) cho rõ ý là ta đang tính trung bình số thực.
        # KHÔNG cộng context_precision/context_recall vào đây: chúng có thể là None
        # (cộng None + số sẽ báo lỗi) và chúng đo retriever chứ không đo câu trả lời.
        return (self.faithfulness + self.relevance + self.completeness) / 3.0


# ---------------------------------------------------------------------------
# Task 2 — RAGAS Evaluator (Simplified word-overlap heuristic)
# ---------------------------------------------------------------------------
# In production, replace with actual RAGAS framework:
#   from ragas import evaluate
#   from ragas.metrics import Faithfulness, AnswerRelevancy, ContextRecall, ContextPrecision
#
# Or DeepEval:
#   from deepeval.metrics import FaithfulnessMetric, AnswerRelevancyMetric
#   assert_test(test_case, [faithfulness, hallucination])
#
# Or TruLens:
#   from trulens.core import Feedback
#   f_groundedness = Feedback(provider.groundedness_measure_with_cot_reasons)
# ---------------------------------------------------------------------------

# Common English stopwords are ignored so overlap reflects *content* words,
# not filler (otherwise "is"/"a"/"the" inflate every score).
STOPWORDS: set[str] = {
    "a",
    "an",
    "the",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "of",
    "in",
    "on",
    "at",
    "to",
    "for",
    "with",
    "as",
    "by",
    "and",
    "or",
    "it",
    "its",
    "this",
    "that",
    "these",
    "those",
    "from",
    "into",
    "than",
}


def _tokenize(text: str) -> set[str]:
    """Lowercase word tokenization, ignoring punctuation and stopwords."""
    if not text:
        return set()
    tokens = re.findall(r"\b\w+\b", text.lower())
    return {t for t in tokens if t not in STOPWORDS}


def _coverage(target_tokens: set[str], source_tokens: set[str]) -> float:
    """Tỉ lệ từ của target_tokens có xuất hiện trong source_tokens.

    Ví dụ: target = {a, b, c, d}, source = {a, b, x}  ->  2/4 = 0.5
    (dấu _ đầu tên = hàm nội bộ, chỉ dùng trong file này)
    """
    # Tập target rỗng thì không có gì để "phủ" -> quy ước trả 1.0.
    # Đồng thời tránh chia cho 0 ở dòng dưới (docstring của lab yêu cầu điều này).
    if not target_tokens:
        return 1.0

    # `&` là phép GIAO của hai set: những từ có mặt ở CẢ HAI tập.
    # len(...) đếm số từ; chia cho số từ của target -> tỉ lệ 0..1.
    score = len(target_tokens & source_tokens) / len(target_tokens)

    # Kẹp về [0.0, 1.0] cho chắc (lab yêu cầu "clamp").
    # min(1.0, x) chặn trần, max(0.0, ...) chặn sàn.
    return max(0.0, min(1.0, score))


def _mean(values: list[float]) -> float:
    """Trung bình cộng; danh sách rỗng thì trả 0.0 để tránh chia cho 0."""
    return sum(values) / len(values) if values else 0.0


# Metric trung bình giảm HƠN mức này so với baseline thì coi là regression (Task 4).
REGRESSION_THRESHOLD = 0.05

# Ngưỡng cho LLMJudge.detect_bias (Task 3). Đây là heuristic đơn giản, không phải chuẩn.
POSITIONAL_BIAS_MARGIN = 0.1  # phản hồi đầu phải hơn trung bình phần còn lại > 0.1
LENIENCY_THRESHOLD = 0.8  # trung bình toàn batch > 0.8 -> judge quá dễ tính
SEVERITY_THRESHOLD = 0.3  # trung bình toàn batch < 0.3 -> judge quá khắt khe


class RAGASEvaluator:
    """
    Evaluates RAG pipeline outputs using RAGAS-inspired heuristics.

    All metrics use word overlap rather than LLM calls for simplicity.
    Replace with actual LLM-based evaluation in production.
    """

    def evaluate_faithfulness(self, answer: str, context: str) -> float:
        """
        Measure how grounded the answer is in the context.

        Heuristic:
            answer_tokens = _tokenize(answer)
            context_tokens = _tokenize(context)
            faithfulness = |answer_tokens ∩ context_tokens| / |answer_tokens|
            Clamp to [0.0, 1.0]. Return 1.0 if answer is empty.

        Returns:
            float in [0.0, 1.0] — 1.0 = fully grounded in context.
        """
        # Bao nhiêu % từ của ANSWER có trong CONTEXT?
        # Từ nào của answer không có trong context = có thể là thông tin bịa.
        return _coverage(_tokenize(answer), _tokenize(context))

    def evaluate_relevance(self, answer: str, question: str) -> float:
        """
        Measure how relevant the answer is to the question.

        Heuristic:
            relevance = |answer_tokens ∩ question_tokens| / |question_tokens|
            Clamp to [0.0, 1.0]. Return 1.0 if question is empty.

        Returns:
            float in [0.0, 1.0]
        """
        # Bao nhiêu % từ của QUESTION được ANSWER nhắc tới?
        # Chú ý thứ tự: target = question, source = answer (khác faithfulness).
        return _coverage(_tokenize(question), _tokenize(answer))

    def evaluate_completeness(self, answer: str, expected: str) -> float:
        """
        Measure how well the answer covers the expected answer.

        Heuristic:
            completeness = |answer_tokens ∩ expected_tokens| / |expected_tokens|
            Clamp to [0.0, 1.0]. Return 1.0 if expected is empty.

        Returns:
            float in [0.0, 1.0]
        """
        # Bao nhiêu % từ của EXPECTED (đáp án chuẩn) có mặt trong ANSWER?
        # Thiếu từ khóa (con số, điều kiện, ngoại lệ) thì điểm giảm.
        return _coverage(_tokenize(expected), _tokenize(answer))

    # -----------------------------------------------------------------------
    # Task 2b — Retrieval-side metrics (evaluate the GET-CONTEXT step)
    # -----------------------------------------------------------------------
    # From lecture (RAG pipeline): Context Recall → Context Precision →
    #   Faithfulness → Answer Relevancy. The two below score the RETRIEVER,
    #   operating on a LIST of chunks (order = retriever rank).
    # -----------------------------------------------------------------------

    def evaluate_context_recall(self, contexts: list[str], expected: str) -> float:
        """Context Recall — how much of the expected answer is covered by the
        UNION of retrieved chunks.

        Heuristic:
            union_tokens = ⋃ _tokenize(chunk) for chunk in contexts
            recall = |expected_tokens ∩ union_tokens| / |expected_tokens|
            Clamp to [0.0, 1.0]. Return 1.0 if expected is empty.

        Low recall => retriever missed evidence the answer needs.
        """
        # "Union" = gộp từ của TẤT CẢ chunk vào một tập.
        # Vì sao gộp? Đáp án có thể cần thông tin từ 2-3 chunk khác nhau;
        # chỉ cần các chunk CỘNG LẠI đủ ý là retriever đã làm tốt.
        union_tokens: set[str] = set()  # bắt đầu bằng tập rỗng
        for chunk in contexts:
            union_tokens |= _tokenize(
                chunk
            )  # |= là "hợp vào tập": thêm từ của chunk này

        # Bao nhiêu % từ của EXPECTED nằm trong kho từ của các chunk?
        # Thấp = retriever bỏ sót evidence.
        return _coverage(_tokenize(expected), union_tokens)

    def evaluate_context_precision(
        self,
        contexts: list[str],
        expected: str,
        relevance_threshold: float = 0.1,
    ) -> float:
        """Context Precision — RANK-AWARE Average Precision (AP@K), like RAGAS.
        Rewards retrievers that place RELEVANT chunks BEFORE noise.

        Steps:
            1. A chunk is "relevant" if it covers >= relevance_threshold of the
               expected tokens:  |chunk ∩ expected| / |expected| >= threshold
            2. Precision@k = (#relevant in top-k) / k
            3. AP@K = (1 / #relevant) * Σ_k [ Precision@k · relevant_k ]

        Return 1.0 if expected empty; 0.0 if no chunks or none relevant.
        Reordering relevant chunks earlier (reranking) raises this score.
        """
        expected_tokens = _tokenize(expected)

        # Hai trường hợp đặc biệt theo docstring:
        if not expected_tokens:  # không có đáp án chuẩn để so -> 1.0
            return 1.0
        if not contexts:  # retriever không trả về chunk nào -> 0.0
            return 0.0

        relevant_seen = 0  # đếm số chunk "liên quan" đã gặp tới lúc này
        precision_sum = (
            0.0  # cộng dồn Precision@k, chỉ tại các vị trí có chunk liên quan
        )

        # enumerate(..., start=1) cho ta thứ hạng rank = 1, 2, 3, ... (không phải 0, 1, 2)
        for rank, chunk in enumerate(contexts, start=1):
            # Chunk "liên quan" nếu nó phủ >= relevance_threshold (mặc định 10%)
            # số từ của expected. Đây chính là coverage của expected bởi chunk.
            if _coverage(expected_tokens, _tokenize(chunk)) >= relevance_threshold:
                relevant_seen += 1
                # Precision@rank = (số chunk liên quan trong top-rank) / rank
                precision_sum += relevant_seen / rank

        # Không có chunk nào liên quan -> 0.0 (cũng tránh chia cho 0 ở dưới)
        if relevant_seen == 0:
            return 0.0

        # AP = trung bình các Precision@k tại vị trí có chunk liên quan
        return precision_sum / relevant_seen

    def run_full_eval(
        self,
        answer: str,
        question: str,
        context: str,
        expected: str,
        contexts: list[str] | None = None,
    ) -> EvalResult:
        """
        Run the three answer-side evaluations and, when ``contexts`` is
        supplied, both retrieval-side evaluations.

        passed = True if all three scores >= 0.5.

        failure_type determination (first match wins):
            faithfulness < 0.3  → "hallucination"
            relevance < 0.3     → "irrelevant"
            completeness < 0.3  → "incomplete"
            otherwise if failed → "off_topic"

        Retrieval wiring:
            contexts is None → context_recall and context_precision stay None
            contexts provided → evaluate and store both retrieval metrics

        The two retrieval metrics diagnose the retriever and do not change the
        three-metric ``passed`` rule or ``overall_score()``.

        Returns:
            EvalResult with all fields populated.
        """
        # --- Bước 1: chấm 3 metric phía câu trả lời (luôn luôn tính) ---
        faithfulness = self.evaluate_faithfulness(answer, context)
        relevance = self.evaluate_relevance(answer, question)
        completeness = self.evaluate_completeness(answer, expected)

        # --- Bước 2: đạt hay rớt? Phải đạt CẢ BA điểm >= 0.5 ---
        # `and` chỉ True khi cả 3 vế True.
        passed = faithfulness >= 0.5 and relevance >= 0.5 and completeness >= 0.5

        # --- Bước 3: nếu rớt, gắn nhãn loại lỗi ---
        # "first match wins": kiểm tra theo THỨ TỰ, khớp cái nào dừng ở cái đó.
        # (elif = chỉ xét nhánh này nếu các nhánh trước sai)
        failure_type: str | None = None  # đạt thì để None
        if not passed:
            if faithfulness < 0.3:
                failure_type = (
                    "hallucination"  # bịa: từ trong answer không có trong context
                )
            elif relevance < 0.3:
                failure_type = "irrelevant"  # lạc đề: không nhắc tới ý của câu hỏi
            elif completeness < 0.3:
                failure_type = "incomplete"  # thiếu ý so với đáp án chuẩn
            else:
                failure_type = "off_topic"  # rớt nhưng không điểm nào < 0.3

        # --- Bước 4: 2 metric retrieval, CHỈ tính khi được cung cấp danh sách chunk ---
        context_recall: float | None = None
        context_precision: float | None = None
        # Dùng `is not None`, KHÔNG viết `if contexts:`. Vì list rỗng [] cũng là "falsy",
        # mà "retriever trả về 0 chunk" là thông tin có thật (điểm phải là 0.0),
        # khác hẳn với "không cung cấp chunk" (điểm phải là None).
        if contexts is not None:
            context_recall = self.evaluate_context_recall(contexts, expected)
            context_precision = self.evaluate_context_precision(contexts, expected)

        # --- Bước 5: đóng gói kết quả ---
        return EvalResult(
            qa_pair=QAPair(
                question=question, expected_answer=expected, context=context
            ),
            actual_answer=answer,
            faithfulness=faithfulness,
            relevance=relevance,
            completeness=completeness,
            passed=passed,
            failure_type=failure_type,
            context_precision=context_precision,  # None nếu không có chunk
            context_recall=context_recall,  # None nếu không có chunk
        )


# ---------------------------------------------------------------------------
# Reranking helper (used by Exercise 3.5 — boosting Context Precision)
# ---------------------------------------------------------------------------


def rerank_by_overlap(contexts: list[str], query: str) -> list[str]:
    """A minimal lexical reranker: sort chunks by word overlap with the query,
    most-overlapping first. Stand-in for a real cross-encoder reranker.

    Reordering relevant chunks toward the top increases the rank-aware
    Context Precision WITHOUT changing the retrieved set.

    Hint: sorted(contexts, key=lambda c: len(_tokenize(c) & _tokenize(query)),
                 reverse=True)
    """
    # Tập từ khóa của truy vấn, tính MỘT lần rồi dùng lại cho mọi chunk.
    query_tokens = _tokenize(query)

    # sorted() trả về list MỚI (không sửa list đầu vào) và là sắp xếp ỔN ĐỊNH:
    # hai chunk có cùng số từ trùng vẫn giữ thứ tự cũ của retriever.
    # key = số từ chung giữa chunk và truy vấn; reverse=True để nhiều từ trùng đứng trước.
    # Chỉ ĐỔI THỨ TỰ, không thêm hay bớt chunk nào, nên tập chunk (union) giữ nguyên.
    return sorted(
        contexts,
        key=lambda chunk: len(_tokenize(chunk) & query_tokens),
        reverse=True,
    )


# ---------------------------------------------------------------------------
# Task 3 — LLM Judge
# ---------------------------------------------------------------------------
# From lecture:
#   - Judge LLM nhận: question + agent answer + reference answer + rubric
#   - Judge trả về: Score 1-5 + Rationale
#   - Best practices: multiple judges, randomize order, calibrate against human
#   - Biases: positional, verbosity, self-preference
#   - Rubric template:
#       5 = Correct, complete, well-cited
#       4 = Mostly correct, minor gaps
#       3 = Partially correct, some errors
#       2 = Significant errors or missing info
#       1 = Wrong or irrelevant
# ---------------------------------------------------------------------------


class LLMJudge:
    """
    Uses an LLM to score AI responses according to a rubric.
    """

    def __init__(self, judge_llm_fn: Callable[[str], str]) -> None:
        # Lưu hàm judge vào self để các method khác (score_response) gọi lại được.
        # Nhờ nhận "một hàm" thay vì gọi thẳng OpenAI, unit test có thể đưa vào
        # hàm giả (mock) và không tốn tiền API.
        self.judge_llm_fn = judge_llm_fn

    def score_response(
        self,
        question: str,
        answer: str,
        rubric: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Score an AI response using the judge LLM.

        Args:
            question: The original question.
            answer:   The AI's answer to score.
            rubric:   Dict mapping criterion name → description.
                      Example: {"accuracy": "Is the answer factually correct?",
                                "clarity": "Is the answer clear and well-structured?"}

        Behavior:
            1. Build a judge prompt that includes the question, answer, and rubric.
            2. Call judge_llm_fn(prompt).
            3. Parse the response for scores.

        For simplicity, if the LLM response can't be parsed as JSON scores,
        return a default score of 0.5 for each criterion.

        Returns:
            {
                "scores":    dict[str, float],  # criterion → score 0-1
                "reasoning": str,               # raw LLM explanation
            }
        """
        # Bước 1: viết prompt gửi cho judge.
        # rubric.items() cho từng cặp (tên tiêu chí, mô tả); mỗi cặp thành một dòng "- tên: mô tả".
        criteria_text = "\n".join(f"- {name}: {desc}" for name, desc in rubric.items())
        prompt = (
            "You are a strict evaluator of customer-support answers.\n\n"
            f"Question:\n{question}\n\n"
            f"Answer to evaluate:\n{answer}\n\n"
            "Score the answer on each criterion below, from 0.0 (worst) to 1.0 (best):\n"
            f"{criteria_text}\n\n"
            "Reply with ONLY a JSON object mapping each criterion name to its score, "
            'for example {"accuracy": 0.8}.'
        )

        # Bước 2: gọi judge. judge_llm_fn là hàm (str -> str) đã lưu ở __init__.
        raw_response = self.judge_llm_fn(prompt)

        # Bước 3: đọc điểm từ câu trả lời của judge.
        # Bắt đầu với điểm mặc định 0.5 cho MỌI tiêu chí (đề bài: parse thất bại thì dùng 0.5).
        scores: dict[str, float] = {name: 0.5 for name in rubric}

        # LLM thật hay bọc JSON trong văn bản, hoặc trong ```json ... ```,
        # nên ta tìm đoạn từ dấu { đầu tiên đến dấu } cuối cùng rồi mới parse.
        # re.DOTALL để dấu "." khớp cả ký tự xuống dòng.
        match = re.search(r"\{.*\}", raw_response, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(0))  # chuỗi JSON -> dict Python
            except json.JSONDecodeError:
                parsed = None  # JSON hỏng -> giữ điểm mặc định
            if isinstance(parsed, dict):
                for name in rubric:
                    try:
                        # float(...) đổi về số thực; max/min kẹp vào [0, 1]
                        scores[name] = max(0.0, min(1.0, float(parsed[name])))
                    except (KeyError, TypeError, ValueError):
                        # judge quên tiêu chí này (KeyError) hoặc trả giá trị không phải số:
                        # giữ nguyên 0.5 cho tiêu chí đó
                        pass

        # "reasoning" giữ nguyên văn bản gốc của judge để sau này đọc lại lý do.
        return {"scores": scores, "reasoning": raw_response}

    def detect_bias(self, scores_batch: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Detect potential bias patterns in a batch of judge scores.

        Checks:
            positional_bias: Check if first response consistently scores higher
            leniency_bias:   Average score > 0.8 across all criteria
            severity_bias:   Average score < 0.3 across all criteria

        Args:
            scores_batch: List of score dicts from score_response().

        Returns:
            {
                "positional_bias": bool,
                "leniency_bias":   bool,
                "severity_bias":   bool,
            }
        """
        # Bước 1: mỗi phần tử trong batch có thể có nhiều tiêu chí.
        # Rút gọn mỗi phần tử thành MỘT số = trung bình các tiêu chí của nó.
        item_averages: list[float] = []
        for item in scores_batch:
            values = list(item.get("scores", {}).values())
            if values:  # bỏ qua phần tử không có điểm nào
                item_averages.append(_mean(values))

        # Batch rỗng thì không đủ dữ liệu để kết luận có bias.
        if not item_averages:
            return {
                "positional_bias": False,
                "leniency_bias": False,
                "severity_bias": False,
            }

        overall_average = _mean(item_averages)  # trung bình toàn batch

        # Positional bias: phản hồi ĐẦU TIÊN được chấm cao hơn hẳn phần còn lại.
        # Cần ít nhất 2 phần tử để so sánh. item_averages[1:] = tất cả trừ phần tử đầu.
        rest = item_averages[1:]
        positional_bias = (
            bool(rest) and item_averages[0] > _mean(rest) + POSITIONAL_BIAS_MARGIN
        )

        return {
            "positional_bias": positional_bias,
            "leniency_bias": overall_average > LENIENCY_THRESHOLD,  # dễ tính
            "severity_bias": overall_average < SEVERITY_THRESHOLD,  # khắt khe
        }


# ---------------------------------------------------------------------------
# Task 4 — Benchmark Runner
# ---------------------------------------------------------------------------
# From lecture:
#   - CI/CD integration: Framework + CI/CD = quality gate tự động
#   - Agent với faithfulness < 0.7 → không được deploy
#   - Regression = metric drop > 0.05 vs baseline
#   - Triggers: mỗi code release, mỗi prompt change, trước demo/launch
# ---------------------------------------------------------------------------


class BenchmarkRunner:
    """
    Runs a full evaluation benchmark.
    """

    def run(
        self,
        qa_pairs: list[QAPair],
        agent_fn: Callable[[str], str],
        evaluator: RAGASEvaluator,
    ) -> list[EvalResult]:
        """
        Run all QA pairs through the agent and evaluate each result.

        Args:
            qa_pairs:   List of QAPair objects.
            agent_fn:   Function str → str (the agent's answer function).
            evaluator:  RAGASEvaluator instance.

        Returns:
            List of EvalResult, one per qa_pair.
        """
        results: list[EvalResult] = []
        for pair in qa_pairs:
            # 1) Hỏi chatbot: agent_fn nhận câu hỏi, trả về câu trả lời (chuỗi).
            answer = agent_fn(pair.question)

            # 2) Chấm điểm câu trả lời. Truyền cả retrieved_contexts để evaluator
            #    tính thêm Context Recall / Precision.
            result = evaluator.run_full_eval(
                answer=answer,
                question=pair.question,
                context=pair.context,
                expected=pair.expected_answer,
                contexts=pair.retrieved_contexts,
            )

            # 3) run_full_eval tự tạo một QAPair tạm (không có metadata: id, difficulty).
            #    Gắn lại QAPair GỐC để evaluate_answers.py còn đọc được result.qa_pair.metadata["id"].
            result.qa_pair = pair
            results.append(result)
        return results

    def generate_report(self, results: list[EvalResult]) -> dict[str, Any]:
        """
        Generate an aggregate report from evaluation results.

        Returns:
            {
                "total":            int,
                "passed":           int,
                "pass_rate":        float,  # passed / total
                "avg_faithfulness": float,
                "avg_relevance":    float,
                "avg_completeness": float,
                "avg_context_recall": float | None,
                "avg_context_precision": float | None,
                "failure_types":    dict[str, int],  # type → count
            }

        Average only non-None retrieval scores. Return None for a retrieval
        average when no result contains that metric.
        """
        total = len(results)
        passed = sum(1 for r in results if r.passed)  # đếm số kết quả đạt

        # Đếm số lần mỗi loại lỗi xuất hiện: {"hallucination": 2, "incomplete": 1, ...}
        failure_types: dict[str, int] = {}
        for r in results:
            if r.failure_type:  # bỏ qua None (câu đạt)
                failure_types[r.failure_type] = failure_types.get(r.failure_type, 0) + 1

        # Chỉ lấy các điểm retrieval KHÁC None để tính trung bình.
        recalls = [r.context_recall for r in results if r.context_recall is not None]
        precisions = [
            r.context_precision for r in results if r.context_precision is not None
        ]

        return {
            "total": total,
            "passed": passed,
            "pass_rate": (
                passed / total if total else 0.0
            ),  # total = 0 thì tránh chia cho 0
            "avg_faithfulness": _mean([r.faithfulness for r in results]),
            "avg_relevance": _mean([r.relevance for r in results]),
            "avg_completeness": _mean([r.completeness for r in results]),
            # Không có điểm nào -> None (khác với 0.0 nghĩa là "có chấm nhưng điểm 0")
            "avg_context_recall": _mean(recalls) if recalls else None,
            "avg_context_precision": _mean(precisions) if precisions else None,
            "failure_types": failure_types,
        }

    def run_regression(self, new_results: list, baseline_results: list) -> dict:
        """Compare new evaluation results against a baseline.

        A regression is when a metric's average drops by more than 0.05 vs baseline.

        Args:
            new_results: List of EvalResult instances (current run)
            baseline_results: List of EvalResult instances (reference/baseline)

        Returns:
            dict with keys:
              - 'new_avg_faithfulness': float
              - 'new_avg_relevance': float
              - 'new_avg_completeness': float
              - 'baseline_avg_faithfulness': float
              - 'baseline_avg_relevance': float
              - 'baseline_avg_completeness': float
              - 'regressions': list[str] — names of metrics that regressed
              - 'passed': bool — True if no regressions

        TODO: Compute avg per metric, compare, list regressions, set passed flag
        """
        report: dict[str, Any] = {}
        regressions: list[str] = []

        # Lặp qua 3 metric answer-side. getattr(r, "faithfulness") tương đương r.faithfulness,
        # nhưng cho phép dùng tên metric (chuỗi) trong vòng lặp.
        for metric in ("faithfulness", "relevance", "completeness"):
            new_avg = _mean([getattr(r, metric) for r in new_results])
            baseline_avg = _mean([getattr(r, metric) for r in baseline_results])
            report[f"new_avg_{metric}"] = new_avg
            report[f"baseline_avg_{metric}"] = baseline_avg

            # Regression = điểm mới THẤP HƠN baseline hơn 0.05 (so sánh chặt ">").
            # round(..., 6) để tránh sai số số thực làm lệch đúng ở biên 0.05.
            if round(baseline_avg - new_avg, 6) > REGRESSION_THRESHOLD:
                regressions.append(metric)  # tên metric KHÔNG có tiền tố "avg_"

        report["regressions"] = regressions
        report["passed"] = (
            not regressions
        )  # danh sách rỗng -> True (không có regression)
        return report

    def identify_failures(
        self,
        results: list[EvalResult],
        threshold: float = 0.5,
    ) -> list[EvalResult]:
        """
        Return EvalResults where any score is below threshold.

        Args:
            results:   Full list of EvalResults.
            threshold: Minimum acceptable score for any metric.

        Returns:
            List of failing EvalResults.
        """
        # min(...) lấy điểm THẤP NHẤT trong 3 metric; nếu điểm thấp nhất còn < threshold
        # thì "có ít nhất một điểm dưới ngưỡng" -> đưa vào danh sách lỗi.
        return [
            r
            for r in results
            if min(r.faithfulness, r.relevance, r.completeness) < threshold
        ]


# ---------------------------------------------------------------------------
# Task 5 — Failure Analyzer
# ---------------------------------------------------------------------------
# From lecture:
#   Failure Taxonomy:
#     - hallucination: bịa thông tin → faithfulness guardrail yếu
#     - irrelevant: không giải quyết câu hỏi → prompt ambiguous
#     - incomplete: bỏ sót thông tin → context window nhỏ, retrieval thiếu
#     - off_topic: trả lời chủ đề khác → intent detection sai
#     - refusal: từ chối khi nên trả lời → guardrails quá chặt
#
#   5 Whys Method: hỏi "Tại sao?" liên tục cho đến root cause
#   Failure Clustering: fix 1 root cause giải quyết nhiều failures cùng lúc
#   Continuous Improvement: Evaluate → Analyze → Improve → Augment → Repeat
# ---------------------------------------------------------------------------

# Một metric dưới ngưỡng này coi là "đang rớt" (cùng ngưỡng với quy tắc passed ở Task 2).
FAIL_THRESHOLD = 0.5

# Bốn kết luận root cause mà find_root_cause được phép trả về (chuỗi lấy nguyên văn từ đề bài).
ROOT_CAUSE_RETRIEVAL = "Context is missing or irrelevant — improve retrieval"
ROOT_CAUSE_PROMPT = "Answer does not address the question — improve prompt clarity"
ROOT_CAUSE_GENERATION = (
    "Answer is missing key information — increase context window or improve generation"
)
ROOT_CAUSE_MULTIPLE = "Multiple issues detected — review full pipeline"

# Gợi ý cải tiến theo từng loại lỗi (failure taxonomy trong bài giảng).
SUGGESTION_BY_FAILURE_TYPE: dict[str, str] = {
    "hallucination": (
        "Implement a hallucination checker that removes claims not supported by the "
        "retrieved context, and tighten the 'use only the retrieved contexts' prompt rule"
    ),
    "irrelevant": (
        "Rewrite the system prompt so the answer addresses every part of the question, "
        "and add few-shot examples of on-target answers"
    ),
    "incomplete": (
        "Increase top_k or chunk size so retrieval returns all needed evidence, and add "
        "few-shot examples of complete answers that keep dates, amounts and exceptions"
    ),
    "off_topic": (
        "Add intent detection / a scope check based on 00_system_scope.md so out-of-scope "
        "questions get a short refusal listing supported topics"
    ),
    "refusal": "Relax over-strict guardrails so answerable questions are not refused",
}

# Gợi ý chung, dùng để bù cho đủ ít nhất 3 gợi ý.
GENERAL_SUGGESTIONS: list[str] = [
    "Add every failed case to the golden dataset as a permanent regression test",
    "Re-run the benchmark after each fix and compare with the baseline using run_regression()",
    "Check Context Recall and Context Precision first to decide whether to fix retrieval or generation",
]


def _table_cell(text: object) -> str:
    """Làm sạch một ô của bảng Markdown: dấu | và xuống dòng sẽ làm vỡ bảng."""
    return str(text).replace("|", "\\|").replace("\n", " ")


class FailureAnalyzer:
    """
    Analyzes failed evaluation results to identify patterns and suggest fixes.
    """

    def categorize_failures(self, failures: list[EvalResult]) -> dict[str, int]:
        """
        Count failures by failure_type.

        Returns:
            dict mapping failure_type → count.
            Example: {"hallucination": 3, "irrelevant": 2, "incomplete": 5}
        """
        counts: dict[str, int] = {}
        for failure in failures:
            # Lỗi chưa có nhãn (None) vẫn được đếm, dưới nhãn "unknown", để không bị mất.
            label = failure.failure_type or "unknown"
            counts[label] = counts.get(label, 0) + 1
        return counts

    def find_root_cause(self, failure: EvalResult) -> str:
        """
        Suggest a root cause for a single failure based on its scores.

        Returns one of these strings based on which score is lowest:
            "Context is missing or irrelevant — improve retrieval"
            "Answer does not address the question — improve prompt clarity"
            "Answer is missing key information — increase context window or improve generation"
            "Multiple issues detected — review full pipeline"
        """
        # TODO: compare faithfulness, relevance, completeness, return appropriate string
        scores = {
            "faithfulness": failure.faithfulness,
            "relevance": failure.relevance,
            "completeness": failure.completeness,
        }

        # Nếu từ 2 metric trở lên cùng rớt thì lỗi không nằm ở một khâu -> xem cả pipeline.
        failing = [name for name, score in scores.items() if score < FAIL_THRESHOLD]
        if len(failing) >= 2:
            return ROOT_CAUSE_MULTIPLE

        # Chỉ một metric rớt: kết luận theo metric THẤP NHẤT.
        # min(dict, key=dict.get) trả về TÊN metric có điểm nhỏ nhất.
        lowest = min(scores, key=scores.get)
        if lowest == "faithfulness":
            return ROOT_CAUSE_RETRIEVAL  # câu trả lời không bám context -> context thiếu/sai
        if lowest == "relevance":
            return ROOT_CAUSE_PROMPT  # không nhắc tới ý câu hỏi -> prompt chưa rõ
        return (
            ROOT_CAUSE_GENERATION  # thiếu ý so với đáp án chuẩn -> generation/context
        )

    def generate_improvement_log(self, failures: list, suggestions: list[str]) -> str:
        """Generate a Markdown table logging failures and improvement actions.

        Format:
        | Failure ID | Type | Root Cause | Suggested Fix | Status |
        |------------|------|------------|---------------|--------|
        | F001       | ...  | ...        | ...           | Open   |

        Args:
            failures: List of EvalResult instances where passed=False
            suggestions: List of suggestion strings (one per failure, can be shorter list)

        Returns:
            Markdown table string with a row per failure. Status is always "Open".

        TODO: Build markdown table with failure details + matched suggestions
        """
        lines = [
            "| Failure ID | Type | Root Cause | Suggested Fix | Status |",
            "|------------|------|------------|---------------|--------|",
        ]
        for index, failure in enumerate(failures, start=1):
            # Gợi ý khớp theo vị trí; hết gợi ý thì lấy gợi ý theo loại lỗi (hoặc câu mặc định).
            if index <= len(suggestions):
                fix = suggestions[index - 1]
            else:
                fix = SUGGESTION_BY_FAILURE_TYPE.get(
                    failure.failure_type, "Investigate this case manually"
                )
            lines.append(
                f"| F{index:03d} "  # F001, F002, ...
                f"| {_table_cell(failure.failure_type or '-')} "
                f"| {_table_cell(self.find_root_cause(failure))} "
                f"| {_table_cell(fix)} "
                "| Open |"  # trạng thái luôn là Open
            )
        return "\n".join(lines)

    def generate_improvement_suggestions(self, failures: list[EvalResult]) -> list[str]:
        """
        Generate a prioritized list of improvement suggestions based on failure patterns.

        Each suggestion should be a concrete, actionable string.

        Examples:
            "Increase chunk size in RAG pipeline to reduce context fragmentation"
            "Add few-shot examples showing complete answers to improve completeness"
            "Implement hallucination checker to filter unsupported claims"

        Returns:
            List of at least 3 suggestion strings (or fewer if failures is empty).
        """
        # TODO: analyze categorized failures and return suggestions
        if not failures:
            return []  # không có lỗi thì không cần gợi ý

        # Bước 1: gợi ý theo loại lỗi, loại XUẤT HIỆN NHIỀU NHẤT đứng trước (ưu tiên).
        # sorted(..., reverse=True) giữ nguyên thứ tự ban đầu khi số lần bằng nhau.
        counts = self.categorize_failures(failures)
        suggestions: list[str] = []
        for failure_type, _count in sorted(
            counts.items(), key=lambda item: item[1], reverse=True
        ):
            if failure_type in SUGGESTION_BY_FAILURE_TYPE:
                suggestions.append(SUGGESTION_BY_FAILURE_TYPE[failure_type])

        # Bước 2: nếu chưa đủ 3 thì bù bằng gợi ý chung (đề bài: ít nhất 3).
        for general in GENERAL_SUGGESTIONS:
            if len(suggestions) >= 3:
                break
            suggestions.append(general)
        return suggestions


# ---------------------------------------------------------------------------
# Entry point for manual testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Sample golden dataset (mini version — use 20 pairs in actual lab)
    # From lecture: stratified sampling = 5 Easy + 7 Medium + 5 Hard + 3 Adversarial
    qa_pairs = [
        # Easy — factual lookup
        QAPair(
            question="What is RAG?",
            expected_answer="RAG stands for Retrieval-Augmented Generation, which combines retrieval with text generation.",
            context="RAG is a technique that retrieves relevant documents and uses them to ground LLM generation.",
            metadata={"difficulty": "easy", "category": "definition"},
        ),
        QAPair(
            question="What is the capital of France?",
            expected_answer="Paris is the capital of France.",
            context="France is a country in Western Europe. Its capital city is Paris.",
            metadata={"difficulty": "easy", "category": "factual"},
        ),
        # Medium — multi-step reasoning
        QAPair(
            question="Explain backpropagation and why it matters for training",
            expected_answer="Backpropagation is an algorithm for training neural networks by computing gradients efficiently, enabling deep learning models to learn from errors.",
            context="Neural networks learn through gradient descent. Backpropagation efficiently computes these gradients layer by layer.",
            metadata={"difficulty": "medium", "category": "explanation"},
        ),
        # Hard — ambiguous
        QAPair(
            question="Should I use RAG or fine-tuning for my chatbot?",
            expected_answer="It depends on the use case: RAG is better for frequently updated knowledge, fine-tuning for consistent style/behavior. Consider cost, latency, and data freshness.",
            context="RAG retrieves external documents at inference time. Fine-tuning modifies model weights during training.",
            metadata={"difficulty": "hard", "category": "comparison"},
        ),
        # Adversarial — out-of-scope
        QAPair(
            question="What is the meaning of life?",
            expected_answer="This question is outside the scope of this system. I can help with AI and technology questions.",
            context="This is an AI assistant specialized in technology topics.",
            metadata={"difficulty": "adversarial", "category": "out_of_scope"},
        ),
    ]

    evaluator = RAGASEvaluator()
    runner = BenchmarkRunner()

    def mock_agent(question: str) -> str:
        """Simple mock agent for testing. Replace with your actual agent."""
        return f"Based on my knowledge: {question[:30]}... The answer involves key concepts."

    # Run benchmark
    results = runner.run(qa_pairs, mock_agent, evaluator)
    report = runner.generate_report(results)
    print("=== Benchmark Report ===")
    for k, v in report.items():
        print(f"  {k}: {v}")

    # Identify and analyze failures
    failures = runner.identify_failures(results, threshold=0.5)
    print(f"\n=== Failures ({len(failures)}) ===")
    analyzer = FailureAnalyzer()

    # Categorize (from lecture: cluster before fix)
    categories = analyzer.categorize_failures(failures)
    print("Failure Categories:", categories)

    # Root cause for each failure (from lecture: 5 Whys)
    for f in failures:
        cause = analyzer.find_root_cause(f)
        print(f"  Root cause: {cause}")

    # Improvement suggestions (from lecture: continuous improvement loop)
    suggestions = analyzer.generate_improvement_suggestions(failures)
    print("\nImprovement Suggestions:")
    for s in suggestions:
        print(f"  - {s}")

    # Generate improvement log (Markdown table)
    log = analyzer.generate_improvement_log(failures, suggestions)
    print("\n=== Improvement Log ===")
    print(log)
