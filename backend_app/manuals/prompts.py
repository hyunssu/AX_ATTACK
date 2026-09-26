TITLE_SUB_SUGGEST_PROMPT = (
    "다음 매뉴얼 제목을 보고, '{category}' 업무 분류 안에서 가장 적합한 소분류 하나를 골라줘.\n\n"
    "[소분류 목록]\n{subs}\n\n"
    "[매뉴얼 제목]\n{title}\n\n"
    "제목만으로 판단하기 어렵거나 맞는 소분류가 없으면 null을 반환해."
)

CHUNK_META_PROMPT = (
    "다음은 매뉴얼에서 잘라낸 한 청크(chunk)야. 이 청크의 섹션 제목과 핵심 키워드를 뽑아줘.\n\n"
    "[청크 내용]\n{chunk_text}"
)

SECTION_CATEGORY_PROMPT = (
    "다음은 '{category}' 업무 매뉴얼로 등록하려고 업로드한 문서에서 잘라낸 한 섹션이야.\n\n"
    "['{category}' 업무 범위]\n{category_definition}\n\n"
    "1. 먼저 이 섹션 내용이 위 범위에 실제로 해당하는지(in_category) 판단해. "
    "문서에 다른 업무 영역 내용이 섞여 있을 수 있으니, 범위와 명확히 관련이 없으면 false로 표시해.\n"
    "2. in_category가 true이면, 아래 소분류 목록 중 이 섹션에 가장 적합한 소분류 하나를 선택해.\n\n"
    "{subs_section}\n\n"
    "먼저 판단의 핵심 근거를 한 문장으로 정리한 뒤 in_category와 소분류를 선택해. "
    "판단이 애매하면 confidence를 'low'로 표시해.\n\n"
    "[섹션 제목]\n{section_title}\n\n[섹션 내용]\n{section_content}"
)
