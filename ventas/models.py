from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse


class Caja(models.Model):
    class Tipo(models.TextChoices):
        MANUAL = 'MANUAL', 'Caja presencial'
        AUTOSERVICIO = 'AUTO', 'Kiosco'
        WEB = 'WEB', 'Venta online'

    nombre = models.CharField(max_length=80, unique=True)
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ['tipo', 'nombre']

    def __str__(self) -> str:
        return self.nombre


class Producto(models.Model):
    nombre = models.CharField(max_length=160)
    categoria = models.CharField(max_length=60, blank=True)
    codigo_vaso = models.CharField(max_length=20, blank=True, help_text='Código normal usado cuando se entrega con vaso.')
    codigo_botella = models.CharField(max_length=20, blank=True, help_text='Código que debe ingresarse si se entrega con botella.')
    descripcion_vaso = models.CharField(max_length=240, blank=True)
    descripcion_botella = models.CharField(max_length=240, blank=True)
    convertible = models.BooleanField(default=False, help_text='Permite transformar automáticamente vaso → botella.')
    confirmado = models.BooleanField(default=False, help_text='Marcar cuando los códigos han sido validados con el negocio.')
    notas = models.TextField(blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ['categoria', 'nombre']

    def clean(self) -> None:
        if self.convertible and (not self.codigo_vaso or not self.codigo_botella):
            raise ValidationError('Un producto convertible debe tener código de vaso y código de botella.')
        if not self.codigo_vaso and not self.codigo_botella:
            raise ValidationError('Ingrese al menos un código de vaso o botella.')

    def __str__(self) -> str:
        return self.nombre

    @property
    def estado_validacion(self) -> str:
        return 'Confirmado' if self.confirmado else 'Por confirmar'


class Jornada(models.Model):
    fecha = models.DateField()
    caja = models.ForeignKey(Caja, on_delete=models.PROTECT, related_name='jornadas')
    observaciones = models.TextField(blank=True)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha', 'caja__nombre']
        constraints = [
            models.UniqueConstraint(fields=['fecha', 'caja'], name='jornada_unica_por_caja_fecha'),
        ]

    def __str__(self) -> str:
        return f'{self.fecha:%d/%m/%Y} - {self.caja.nombre}'

    def get_absolute_url(self):
        return reverse('jornada_detalle', args=[self.pk])


class Cierre(models.Model):
    class Modalidad(models.TextChoices):
        VASO = 'VASO', 'Venta normal: mantener vaso'
        BOTELLA = 'BOTELLA', 'Entrega con botella: convertir productos aplicables'

    jornada = models.ForeignKey(Jornada, on_delete=models.CASCADE, related_name='cierres')
    numero = models.PositiveIntegerField(help_text='Orden del cierre dentro del día: 1, 2, 3...')
    modalidad_periodo = models.CharField(
        max_length=12,
        choices=Modalidad.choices,
        default=Modalidad.VASO,
        help_text='Presentación entregada en las ventas ocurridas desde el cierre anterior hasta este cierre.',
    )
    motivo_cambio = models.CharField(max_length=180, blank=True, help_text='Ejemplo: agotamiento de jarabe.')
    imagen = models.ImageField(upload_to='cierres/%Y/%m/%d/', blank=True, null=True)
    ocr_texto = models.TextField(blank=True)
    ocr_estado = models.CharField(max_length=240, blank=True)
    productos_convertir = models.ManyToManyField(
        Producto,
        blank=True,
        related_name='cierres_convertidos',
        help_text='Opcional: si se deja vacío, se convierten todos los productos convertibles del periodo botella.',
    )
    confirmado = models.BooleanField(default=False)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['numero']
        constraints = [
            models.UniqueConstraint(fields=['jornada', 'numero'], name='numero_cierre_unico_en_jornada'),
        ]

    def __str__(self) -> str:
        return f'Cierre {self.numero} - {self.jornada}'

    @property
    def etiqueta_modalidad(self) -> str:
        return 'Botella' if self.modalidad_periodo == self.Modalidad.BOTELLA else 'Vaso'


class DetalleCierre(models.Model):
    cierre = models.ForeignKey(Cierre, on_delete=models.CASCADE, related_name='detalles')
    codigo_leido = models.CharField(max_length=20)
    cantidad_acumulada = models.PositiveIntegerField()

    class Meta:
        ordering = ['codigo_leido']
        constraints = [
            models.UniqueConstraint(fields=['cierre', 'codigo_leido'], name='codigo_unico_por_cierre'),
        ]

    def __str__(self) -> str:
        return f'{self.codigo_leido}: {self.cantidad_acumulada}'
