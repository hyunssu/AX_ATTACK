1. 저장소 생성 및 연결

#### 저장소 초기화

```
git init
```

#### 원격 저장소 연결

```
git remote add origin <repository-url>
```

#### 원격 저장소 확인

```
git remote -v
```

#### 원격 저장소 URL 변경

```
git remote set-url origin <repository-url>
```

2. Clone

#### 원격 저장소 가져오기

```
git clone <repository-url>
```

예:
git clone https://github.com/user/project.git

3. 상태 확인

#### 변경 파일 확인

```
git status
```

#### 커밋 이력 확인

```
git log
한 줄로 보기
git log --oneline
```

4. Commit

```
전체 파일 추가
git add .
특정 파일 추가
git add test.java
Commit
git commit -m "메시지"
```

```
5. Push
최초 Push
git push -u origin main
이후 Push
git push
```

6. Pull

```
최신 소스 받기
git pull
```

특정 브랜치
git pull origin main

7. Branch

#### 브랜치 조회

git branch

#### 원격 포함 조회

git branch -a

#### 브랜치 생성

git branch feature/test

#### 브랜치 이동

git checkout feature/test

또는

git switch feature/test
생성 후 이동
git checkout -b feature/test
브랜치 삭제
git branch -d feature/test 8. Merge
main으로 이동
git checkout main
병합
git merge feature/test 9. Fetch
원격 정보만 가져오기
git fetch
원격 브랜치 확인
git branch -r 10. 되돌리기
add 취소
git restore --staged 파일명
파일 수정 취소
git restore 파일명
마지막 커밋 취소(로컬만)
git reset --soft HEAD~1
커밋+스테이징 모두 취소
git reset --hard HEAD~1 11. 태그
태그 생성
git tag v1.0
태그 조회
git tag
태그 Push
git push origin v1.0
실무에서 제일 많이 쓰는 순서
git pull
git checkout -b feature/abc

# 개발

git add .
git commit -m "Add abc feature"
git push -u origin feature/abc

이후 GitHu
