import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { perfilPrueba } from '../mock/perfiles-prueba';
import { Perfil } from './Perfil';

afterEach(cleanup);

describe('ficha con datos reales incompletos', () => {
  it('admite nombre, categoría y fecha ausentes sin romperse ni mostrar encaje sin brief', () => {
    render(<Perfil perfil={{ ...perfilPrueba, nombre: null, bio: null, categoria: null, encaje: null, marcas: [{ ...perfilPrueba.marcas[0], fecha: null }] }} cerrar={vi.fn()} />);
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText(perfilPrueba.marcas[0].nombre)).toBeInTheDocument();
    expect(screen.queryByText('Encaje con el brief')).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('—');
  });

  it('explica audiencia de contenido sin atribuirla a una muestra de seguidores', () => {
    render(<Perfil perfil={{ ...perfilPrueba, seguidores_muestra: 0, audiencia: { ...perfilPrueba.audiencia, fuente: 'contenido' } }} conBrief cerrar={vi.fn()} />);
    expect(screen.getByText('Estimado por IA a partir del contenido del perfil. Sin muestra de seguidores.')).toBeInTheDocument();
    expect(screen.getByText('Encaje con el brief')).toBeInTheDocument();
  });

  it('muestra edad por género y lugares con la probabilidad de la IA, como el panel de Instagram', () => {
    const estimacion = {
      genero: { Female: 0.7, Male: 0.3 },
      edad: { '18-24': 0.1, '25-34': 0.9 },
      edad_genero: { '18-24': { Female: 0.08, Male: 0.02 }, '25-34': { Female: 0.6, Male: 0.3 } },
      ciudad: { Lima: 0.9, Bogotá: 0.1 },
      pais: { Perú: 0.9, Colombia: 0.1 },
    };
    render(<Perfil perfil={{ ...perfilPrueba, audiencia: { ...perfilPrueba.audiencia, estimacion } }} cerrar={vi.fn()} />);
    expect(screen.getByLabelText('25-34 años: 90 % (mujeres 60 %, hombres 30 %)')).toBeInTheDocument();
    expect(screen.getByRole('list', { name: 'Países de la audiencia' })).toHaveTextContent('Perú90 %');
    fireEvent.click(screen.getByRole('button', { name: 'Ciudades' }));
    expect(screen.getByRole('list', { name: 'Ciudades de la audiencia' })).toHaveTextContent('Bogotá10 %');
    expect(screen.getByText(/no el porcentaje de seguidores/)).toBeInTheDocument();
  });
});
