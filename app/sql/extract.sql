WITH changed AS (
 SELECT q.id AS question_id, q.title, q.body AS question_body,
        q.owner_user_id AS question_author_id,
        a.id AS answer_id, a.body AS answer_body, a.owner_user_id AS answer_author_id,
        GREATEST(q.last_activity_date, COALESCE(a.last_activity_date, q.last_activity_date)) AS updated_at
 FROM `bigquery-public-data.stackoverflow.posts_questions` q
 LEFT JOIN `bigquery-public-data.stackoverflow.posts_answers` a ON q.accepted_answer_id=a.id
)
SELECT * FROM changed
WHERE (updated_at > @cursor_time OR (updated_at = @cursor_time AND question_id > @cursor_id))
  AND updated_at <= @upper_bound
ORDER BY updated_at, question_id
LIMIT @limit
