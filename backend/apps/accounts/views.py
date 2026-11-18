from typing import cast

from rest_framework.generics import RetrieveUpdateAPIView

from .models import User
from .serializers import MeSerializer


class MeView(RetrieveUpdateAPIView):
    """O perfil do usuário autenticado. Não recebe id: só existe "o meu".

    Permissão: o padrão do projeto (IsAuthenticated). PUT fica de fora; só GET e PATCH.
    """

    serializer_class = MeSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self) -> User:
        return cast(User, self.request.user)
