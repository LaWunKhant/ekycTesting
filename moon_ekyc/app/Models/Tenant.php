<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Str;

class Tenant extends Model
{
    protected $table = 'tenants';

    protected $fillable = [
        'name',
        'slug',
        'uuid',
        'is_active',
        'plan',
    ];

    protected function casts(): array
    {
        return [
            'is_active' => 'boolean',
            'created_at' => 'datetime',
            'updated_at' => 'datetime',
            'deleted_at' => 'datetime',
            'suspended_at' => 'datetime',
        ];
    }

    public function staffUsers(): HasMany
    {
        return $this->hasMany(User::class);
    }

    public static function resolveFromHost(string $host): ?self
    {
        if (! Schema::hasTable((new static)->getTable())) {
            return null;
        }

        $slug = static::slugFromHost($host);

        if ($slug === '') {
            return null;
        }

        return static::query()
            ->where('slug', $slug)
            ->where('is_active', true)
            ->first();
    }

    public static function hasTenantTable(): bool
    {
        return Schema::hasTable((new static)->getTable());
    }

    private static function slugFromHost(string $host): string
    {
        $normalizedHost = Str::before(Str::lower($host), ':');
        $segments = array_values(array_filter(explode('.', $normalizedHost)));

        return $segments[0] ?? '';
    }
}
