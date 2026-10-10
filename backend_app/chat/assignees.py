"""담당자 질문에 users의 업무 키워드 프로필로 답한다."""
import re
from auth.profiles import read_profiles


def is_assignee_question(question):
    return bool(re.search(r"(?:담당자|담당팀|담당부서).*(?:누구|어디|찾|알려|검색|있|확인)|(?:누가|어느\s*팀).*(?:담당|책임)|(?:who|which\s+team).*(?:responsible|in\s+charge)|(?:담당자|담당팀|담당부서)[?？]?\s*$", question, re.I))


def answer_assignee_question(question, language='ko'):
    query = re.sub(r'\s+', '', question).casefold()
    matches = []
    for profile in read_profiles():
        matched = [keyword for keyword in profile['expertise_keywords'] if keyword.strip() and re.sub(r'\s+', '', keyword).casefold() in query]
        if matched:
            matches.append((len(matched), profile, matched))
    if not matches:
        return {'type': 'answer', 'answerable': False, 'text': '해당 업무 키워드로 담당자를 찾지 못했습니다.', 'options': [], 'sources': []}
    matches.sort(key=lambda item: (-item[0], item[1]['username']))
    lines = []
    for _, profile, keywords in matches:
        name = profile.get('display_name') or profile['username']
        country = ', '.join(profile['countries']) or ('미확인' if language == 'ko' else 'Unknown')
        department = profile.get('department') or ('미확인' if language == 'ko' else 'Unknown')
        lines.append(f"담당자: {name} ({profile['username']})\n담당팀: {department}\n담당 국가: {country}\n검색 키워드: {', '.join(keywords)}" if language == 'ko' else f"Assignee: {name} ({profile['username']})\nTeam: {department}\nCountries: {country}\nMatched keywords: {', '.join(keywords)}")
    return {'type': 'answer', 'answerable': True, 'text': '\n\n'.join(lines), 'options': [], 'sources': [], 'trace': {'engine': 'user_profiles', 'steps': [{'node': 'search_assignee_keywords', 'input': {'question': question}, 'output': {'usernames': [item[1]['username'] for item in matches]}}]}}
