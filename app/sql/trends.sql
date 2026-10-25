WITH counts AS (
 SELECT DATE_TRUNC(DATE(creation_date), MONTH) AS month,
        COUNT(*) AS questions, COUNTIF(accepted_answer_id IS NOT NULL) AS accepted,
        MAX(last_activity_date) AS latest_matching_activity
 FROM `bigquery-public-data.stackoverflow.posts_questions`
 WHERE @tag IN UNNEST(SPLIT(tags, '|'))
   AND DATE(creation_date) >= DATE_TRUNC(DATE_SUB(CURRENT_DATE('UTC'), INTERVAL @months MONTH), MONTH)
   AND DATE(creation_date) < DATE_TRUNC(CURRENT_DATE('UTC'), MONTH)
 GROUP BY month
), calendar AS (
 SELECT month FROM UNNEST(GENERATE_DATE_ARRAY(
   DATE_TRUNC(DATE_SUB(CURRENT_DATE('UTC'), INTERVAL @months MONTH), MONTH),
   DATE_SUB(DATE_TRUNC(CURRENT_DATE('UTC'), MONTH), INTERVAL 1 MONTH), INTERVAL 1 MONTH)) month
)
SELECT month, COALESCE(questions,0) AS questions, COALESCE(accepted,0) AS accepted, latest_matching_activity
FROM calendar LEFT JOIN counts USING(month) ORDER BY month
