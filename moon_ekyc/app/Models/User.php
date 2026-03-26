<?php

namespace App\Models;

// use Illuminate\Contracts\Auth\MustVerifyEmail;
use Illuminate\Database\Eloquent\Casts\Attribute;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Foundation\Auth\User as Authenticatable;
use Illuminate\Notifications\Notifiable;
use Illuminate\Support\Facades\Hash;

class User extends Authenticatable
{
    /** @use HasFactory<\Database\Factories\UserFactory> */
    use HasFactory, Notifiable;

    protected $table = 'staff_users';

    protected $appends = [
        'name',
    ];

    /**
     * The attributes that are mass assignable.
     *
     * @var list<string>
     */
    protected $fillable = [
        'first_name',
        'last_name',
        'email',
        'password',
        'role',
        'tenant_id',
        'is_active',
        'is_staff',
        'is_superuser',
    ];

    /**
     * The attributes that should be hidden for serialization.
     *
     * @var list<string>
     */
    protected $hidden = [
        'password',
    ];

    /**
     * Get the attributes that should be cast.
     *
     * @return array<string, string>
     */
    protected function casts(): array
    {
        return [
            'last_login' => 'datetime',
            'date_joined' => 'datetime',
            'is_active' => 'boolean',
            'is_staff' => 'boolean',
            'is_superuser' => 'boolean',
        ];
    }

    protected function name(): Attribute
    {
        return Attribute::get(function (): string {
            $name = trim("{$this->first_name} {$this->last_name}");

            return $name !== '' ? $name : $this->email;
        });
    }

    public function tenant(): BelongsTo
    {
        return $this->belongsTo(Tenant::class);
    }

    public function canAuthenticateWithPassword(string $plainPassword): bool
    {
        if ($this->password === null || $this->password === '') {
            return false;
        }

        if (str_starts_with($this->password, 'pbkdf2_sha256$')) {
            return $this->checkDjangoPbkdf2Sha256($plainPassword, $this->password);
        }

        if (str_starts_with($this->password, '$2y$') || str_starts_with($this->password, '$2b$') || str_starts_with($this->password, '$argon2')) {
            return Hash::check($plainPassword, $this->password);
        }

        return false;
    }

    private function checkDjangoPbkdf2Sha256(string $plainPassword, string $encodedPassword): bool
    {
        [$algorithm, $iterations, $salt, $hash] = explode('$', $encodedPassword, 4);

        if ($algorithm !== 'pbkdf2_sha256' || ! is_numeric($iterations)) {
            return false;
        }

        $derived = base64_encode(hash_pbkdf2('sha256', $plainPassword, $salt, (int) $iterations, 32, true));

        return hash_equals($hash, $derived);
    }
}
