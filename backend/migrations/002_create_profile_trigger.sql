-- Crea automáticamente la fila de profiles cuando se crea un usuario en auth.users.
-- Corre con privilegios del owner (SECURITY DEFINER) para poder escribir en
-- profiles pese a RLS, y en la MISMA transacción que el INSERT en auth.users
-- (atomicidad real: si esto falla, también falla la creación del usuario).
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  INSERT INTO public.profiles (id, full_name, phone)
  VALUES (
    NEW.id,
    NEW.raw_user_meta_data ->> 'full_name',
    NEW.raw_user_meta_data ->> 'phone'
  );
  RETURN NEW;
END;
$$;

CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW
  EXECUTE FUNCTION public.handle_new_user();
