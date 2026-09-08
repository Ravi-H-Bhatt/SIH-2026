-- Legacy RLS policies dropped by scripts/migrate_users_to_orm.py
-- Replay this file to restore them (requires users.role to be user_role enum again).

CREATE POLICY "audit_read" ON public."audit_events"
  AS PERMISSIVE
  FOR SELECT
  TO public
  USING ((EXISTS ( SELECT 1
   FROM users
  WHERE ((users.auth_user_id = auth.uid()) AND (users.role = ANY (ARRAY['AUDITOR'::user_role, 'ADMIN'::user_role]))))));

CREATE POLICY "documents_access" ON public."documents"
  AS PERMISSIVE
  FOR ALL
  TO public
  USING ((screening_id IN ( SELECT screenings.id
   FROM screenings
  WHERE ((screenings.officer_id IN ( SELECT users.id
           FROM users
          WHERE (users.auth_user_id = auth.uid()))) OR (EXISTS ( SELECT 1
           FROM users
          WHERE ((users.auth_user_id = auth.uid()) AND (users.role = ANY (ARRAY['SUPERVISOR'::user_role, 'ADMIN'::user_role, 'ANALYST'::user_role])))))))));

CREATE POLICY "face_captures_access" ON public."face_captures"
  AS PERMISSIVE
  FOR ALL
  TO public
  USING ((screening_id IN ( SELECT screenings.id
   FROM screenings
  WHERE ((screenings.officer_id IN ( SELECT users.id
           FROM users
          WHERE (users.auth_user_id = auth.uid()))) OR (EXISTS ( SELECT 1
           FROM users
          WHERE ((users.auth_user_id = auth.uid()) AND (users.role = ANY (ARRAY['SUPERVISOR'::user_role, 'ADMIN'::user_role, 'ANALYST'::user_role])))))))));

CREATE POLICY "face_verification_access" ON public."face_verification_results"
  AS PERMISSIVE
  FOR ALL
  TO public
  USING ((screening_id IN ( SELECT screenings.id
   FROM screenings
  WHERE ((screenings.officer_id IN ( SELECT users.id
           FROM users
          WHERE (users.auth_user_id = auth.uid()))) OR (EXISTS ( SELECT 1
           FROM users
          WHERE ((users.auth_user_id = auth.uid()) AND (users.role = ANY (ARRAY['SUPERVISOR'::user_role, 'ADMIN'::user_role, 'ANALYST'::user_role])))))))));

CREATE POLICY "forensics_access" ON public."forensic_results"
  AS PERMISSIVE
  FOR ALL
  TO public
  USING ((screening_id IN ( SELECT screenings.id
   FROM screenings
  WHERE ((screenings.officer_id IN ( SELECT users.id
           FROM users
          WHERE (users.auth_user_id = auth.uid()))) OR (EXISTS ( SELECT 1
           FROM users
          WHERE ((users.auth_user_id = auth.uid()) AND (users.role = ANY (ARRAY['SUPERVISOR'::user_role, 'ADMIN'::user_role, 'ANALYST'::user_role])))))))));

CREATE POLICY "mrz_access" ON public."mrz_records"
  AS PERMISSIVE
  FOR ALL
  TO public
  USING ((screening_id IN ( SELECT screenings.id
   FROM screenings
  WHERE ((screenings.officer_id IN ( SELECT users.id
           FROM users
          WHERE (users.auth_user_id = auth.uid()))) OR (EXISTS ( SELECT 1
           FROM users
          WHERE ((users.auth_user_id = auth.uid()) AND (users.role = ANY (ARRAY['SUPERVISOR'::user_role, 'ADMIN'::user_role, 'ANALYST'::user_role])))))))));

CREATE POLICY "ocr_access" ON public."ocr_results"
  AS PERMISSIVE
  FOR ALL
  TO public
  USING ((screening_id IN ( SELECT screenings.id
   FROM screenings
  WHERE ((screenings.officer_id IN ( SELECT users.id
           FROM users
          WHERE (users.auth_user_id = auth.uid()))) OR (EXISTS ( SELECT 1
           FROM users
          WHERE ((users.auth_user_id = auth.uid()) AND (users.role = ANY (ARRAY['SUPERVISOR'::user_role, 'ADMIN'::user_role, 'ANALYST'::user_role])))))))));

CREATE POLICY "screenings_select" ON public."screenings"
  AS PERMISSIVE
  FOR SELECT
  TO public
  USING (((officer_id IN ( SELECT users.id
   FROM users
  WHERE (users.auth_user_id = auth.uid()))) OR (EXISTS ( SELECT 1
   FROM users u
  WHERE ((u.auth_user_id = auth.uid()) AND ((u.role = ANY (ARRAY['SUPERVISOR'::user_role, 'ADMIN'::user_role])) OR (u.role = 'ANALYST'::user_role)))))));

CREATE POLICY "screenings_update" ON public."screenings"
  AS PERMISSIVE
  FOR UPDATE
  TO public
  USING (((officer_id IN ( SELECT users.id
   FROM users
  WHERE (users.auth_user_id = auth.uid()))) OR (EXISTS ( SELECT 1
   FROM users
  WHERE ((users.auth_user_id = auth.uid()) AND (users.role = ANY (ARRAY['SUPERVISOR'::user_role, 'ADMIN'::user_role])))))));

CREATE POLICY "users_select_own" ON public."users"
  AS PERMISSIVE
  FOR SELECT
  TO public
  USING (((auth.uid() = auth_user_id) OR (EXISTS ( SELECT 1
   FROM users users_1
  WHERE ((users_1.auth_user_id = auth.uid()) AND (users_1.role = 'ADMIN'::user_role))))));

CREATE POLICY "users_update_own" ON public."users"
  AS PERMISSIVE
  FOR UPDATE
  TO public
  USING (((auth.uid() = auth_user_id) OR (EXISTS ( SELECT 1
   FROM users users_1
  WHERE ((users_1.auth_user_id = auth.uid()) AND (users_1.role = 'ADMIN'::user_role))))));

CREATE POLICY "validation_access" ON public."validation_results"
  AS PERMISSIVE
  FOR ALL
  TO public
  USING ((screening_id IN ( SELECT screenings.id
   FROM screenings
  WHERE ((screenings.officer_id IN ( SELECT users.id
           FROM users
          WHERE (users.auth_user_id = auth.uid()))) OR (EXISTS ( SELECT 1
           FROM users
          WHERE ((users.auth_user_id = auth.uid()) AND (users.role = ANY (ARRAY['SUPERVISOR'::user_role, 'ADMIN'::user_role, 'ANALYST'::user_role])))))))));

CREATE POLICY "watchlist_modify" ON public."watchlist_entries"
  AS PERMISSIVE
  FOR ALL
  TO public
  USING ((EXISTS ( SELECT 1
   FROM users
  WHERE ((users.auth_user_id = auth.uid()) AND (users.role = 'ADMIN'::user_role)))));

CREATE POLICY "watchlist_read" ON public."watchlist_entries"
  AS PERMISSIVE
  FOR SELECT
  TO public
  USING ((EXISTS ( SELECT 1
   FROM users
  WHERE ((users.auth_user_id = auth.uid()) AND (users.role = ANY (ARRAY['ANALYST'::user_role, 'SUPERVISOR'::user_role, 'ADMIN'::user_role]))))));
